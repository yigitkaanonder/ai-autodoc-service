import os
import hashlib
from tree_sitter_languages import get_parser


# Map file extensions to tree-sitter language names
EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".go": "go",
    ".java": "java",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".h": "cpp",
    ".hpp": "cpp",
}

# Node types that represent functions/methods in each language.
# tree-sitter uses different node type names per grammar.
FUNCTION_NODE_TYPES = {
    "python": [
        "function_definition",       # def foo(): / async def foo():
    ],
    "javascript": [
        "function_declaration",      # function foo() {}
        "method_definition",         # class method
        "arrow_function",            # const foo = () => {}
        "function",                  # const foo = function() {}
        "generator_function_declaration",  # function* foo() {}
    ],
    "typescript": [
        "function_declaration",
        "method_definition",
        "arrow_function",
        "function",
        "generator_function_declaration",
    ],
    "go": [
        "function_declaration",      # func foo() {}
        "method_declaration",        # func (r *Receiver) foo() {}
    ],
    "java": [
        "method_declaration",        # public void foo() {}
        "constructor_declaration",   # public MyClass() {}
    ],
    "cpp": [
        "function_definition",       # int foo() {}
    ],
}


#   python      call                -> function: identifier | attribute(.attribute)
#   js/ts       call_expression     -> function: identifier | member_expression(.property)
#   go          call_expression     -> function: identifier | selector_expression(.field)
#   java        method_invocation   -> name: identifier
#               object_creation_expression (new Foo()) -> type: type_identifier
#   cpp         call_expression     -> function: identifier | field_expression(.field)
#                                                  | qualified_identifier(.name)
CALL_NODE_TYPES = {
    "python": {"call"},
    "javascript": {"call_expression"},
    "typescript": {"call_expression"},
    "go": {"call_expression"},
    "java": {"method_invocation", "object_creation_expression"},
    "cpp": {"call_expression"},
}


def get_language(file_path: str):
    """Determine tree-sitter language name from file extension."""
    ext = os.path.splitext(file_path)[1].lower()
    return EXTENSION_TO_LANGUAGE.get(ext)


def _get_function_name(node, language):
    """
    Extract function name from a tree-sitter node.
    Different languages and node types store the name in different places.
    """
    node_type = node.type

    # --- JS/TS: arrow_function / function_expression ---
    # These don't have a 'name' field themselves.
    # The name lives on the parent variable_declarator:
    #   (variable_declarator name: (identifier) value: (arrow_function ...))
    if node_type in ("arrow_function", "function"):
        parent = node.parent
        if parent and parent.type == "variable_declarator":
            name_node = parent.child_by_field_name("name")
            if name_node:
                return name_node.text.decode("utf-8")
        # Anonymous function (e.g. passed as callback) — skip
        return None

    # --- C++: function_definition ---
    # Name is buried inside a declarator chain:
    #   (function_definition
    #     type: (primitive_type)
    #     declarator: (function_declarator
    #       declarator: (identifier)    <-- name is here
    #       parameters: ...))
    if language == "cpp" and node_type == "function_definition":
        return _extract_cpp_function_name(node)

    # --- General case (Python, Go, Java, JS/TS declarations) ---
    # Most function nodes have a direct 'name' child field.
    name_node = node.child_by_field_name("name")
    if name_node:
        return name_node.text.decode("utf-8")

    return None


def _extract_cpp_function_name(node):
    """
    C++ function_definition has a nested declarator structure.
    Dig through it to find the actual function name.
    """
    declarator = node.child_by_field_name("declarator")
    if not declarator:
        return None

    # function_declarator wraps the name + parameters
    if declarator.type == "function_declarator":
        inner = declarator.child_by_field_name("declarator")
        if inner:
            # Could be plain identifier, qualified name (Foo::bar), etc.
            return inner.text.decode("utf-8")

    # Reference declarator: int& foo() — one extra wrapper
    if declarator.type == "reference_declarator":
        func_decl = declarator.children[0] if declarator.children else None
        if func_decl and func_decl.type == "function_declarator":
            inner = func_decl.child_by_field_name("declarator")
            if inner:
                return inner.text.decode("utf-8")

    # Pointer declarator: int* foo()
    if declarator.type == "pointer_declarator":
        func_decl = declarator.child_by_field_name("declarator")
        if func_decl and func_decl.type == "function_declarator":
            inner = func_decl.child_by_field_name("declarator")
            if inner:
                return inner.text.decode("utf-8")

    return None


def _get_callee_name(node, language):
    """
    Given a call node, return the simple name of the function being called,
    or None if it can't be determined (dynamic/computed callee, etc.).
 
    "Simple name" means the final identifier only: `Foo::bar()` -> "bar",
    `obj.method()` -> "method", `mod.sub.fn()` -> "fn". Resolution in
    call_graph.py normalizes definition names the same way, so a call and its
    definition line up regardless of qualifier.
    """
    node_type = node.type
 
    # Java is the odd one out: calls expose the method name on a 'name' field,
    # and `new Foo()` is a separate node whose 'type' field is the class.
    if language == "java":
        if node_type == "method_invocation":
            name_node = node.child_by_field_name("name")
            return name_node.text.decode("utf-8") if name_node else None
        if node_type == "object_creation_expression":  # new Foo(...)
            type_node = node.child_by_field_name("type")
            return type_node.text.decode("utf-8") if type_node else None
        return None
 
    # Everything else nests the callee under a 'function' field.
    func = node.child_by_field_name("function")
    if func is None:
        return None
    ftype = func.type
 
    if ftype == "identifier":                       # foo()
        return func.text.decode("utf-8")
 
    if language == "python" and ftype == "attribute":          # obj.method()
        attr = func.child_by_field_name("attribute")
        return attr.text.decode("utf-8") if attr else None
 
    if language in ("javascript", "typescript") and ftype == "member_expression":  # obj.method()
        prop = func.child_by_field_name("property")
        return prop.text.decode("utf-8") if prop else None
 
    if language == "go" and ftype == "selector_expression":    # pkg.Fn() / recv.Method()
        field = func.child_by_field_name("field")
        return field.text.decode("utf-8") if field else None
 
    if language == "cpp" and ftype == "field_expression":      # obj.method()
        field = func.child_by_field_name("field")
        return field.text.decode("utf-8") if field else None
 
    if language == "cpp" and ftype == "qualified_identifier":  # Foo::bar()
        name_node = func.child_by_field_name("name")
        return name_node.text.decode("utf-8") if name_node else None
 
    return None
 
 
def _collect_callees(fn_node, language):
    """
    Names of functions called directly within fn_node.
 
    Crucially, we do NOT descend into nested function *definitions*: a call
    inside a nested `def`/arrow/method belongs to that nested function (which is
    extracted as its own unit), not to its enclosing function. Lambdas are not
    function definitions, so calls inside an inline lambda are attributed to the
    enclosing function (intentional — the lambda is part of its body).
 
    Returns a de-duplicated, order-preserving list of simple callee names.
    """
    func_types = set(FUNCTION_NODE_TYPES.get(language, []))
    call_types = CALL_NODE_TYPES.get(language, set())
    seen = set()
    ordered = []
 
    def recurse(node, is_root):
        # Stop at a nested function-definition boundary (but never at the root).
        if not is_root and node.type in func_types:
            return
        if node.type in call_types:
            name = _get_callee_name(node, language)
            if name and name not in seen:
                seen.add(name)
                ordered.append(name)
        for child in node.children:
            recurse(child, False)
 
    recurse(fn_node, True)
    return ordered


def _walk_tree(node):
    """Recursively yield all nodes in the syntax tree (depth-first)."""
    yield node
    for child in node.children:
        yield from _walk_tree(child)


def extract_functions(code: str, file_path: str) -> list:
    """
    Parse source code with tree-sitter and extract functions.

    Args:
        code: The source code as a string.
        file_path: File path (used to determine language from extension).

    Returns:
        List of dicts: [{"name": str, "source": str, "hash": str, "file_path": str, 
                            "language": str, "callees": list, "has_error": bool}, ...]
    """
    language = get_language(file_path)
    if not language:
        return []

    parser = get_parser(language)
    code_bytes = code.encode("utf-8")
    tree = parser.parse(code_bytes)

    target_types = set(FUNCTION_NODE_TYPES.get(language, []))
    functions = []

    for node in _walk_tree(tree.root_node):
        if node.type not in target_types:
            continue

        name = _get_function_name(node, language)
        if not name:
            continue

        source = node.text.decode("utf-8")
        content_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()

        functions.append({
            "name": name,
            "source": source,
            "hash": content_hash,
            "file_path": file_path,
            "language": language,
            "callees": _collect_callees(node, language),
            "has_error": node.has_error,
        })

    return functions
