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
        List of dicts: [{"name": str, "source": str, "hash": str}, ...]
        Same format as the old ast_parser so callers don't need to change their logic.
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
        })

    return functions
