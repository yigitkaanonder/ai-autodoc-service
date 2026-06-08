import ast
import hashlib


def extract_functions(code: str) -> list:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        # If code can't be parsed, return empty
        return []

    functions = []
    lines = code.splitlines()

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Get the source lines of this function
            start = node.lineno - 1
            end = node.end_lineno
            source = "\n".join(lines[start:end])

            content_hash = hashlib.sha256(source.encode("utf-8")).hexdigest() #hasher

            functions.append({
                "name": node.name,
                "source": source,
                "hash": content_hash
            })

    return functions #returns a list of dicts with func name, source, hash.