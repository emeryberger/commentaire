import openai
import os
import sys
import ast

def update_args(old_function_ast, new_function_ast):
    # Get the list of argument names from the old function AST
    arg_names = [arg.arg for arg in old_function_ast.args.args]
    
    # Create a new argument list with the same argument names and updated annotations
    new_args = []
    for arg in new_function_ast.args.args:
        if arg.arg in arg_names:
            # If the argument is in the old argument list, use the new annotation
            old_arg = old_function_ast.args.args[arg_names.index(arg.arg)]
            new_arg = ast.arg(arg=arg.arg, annotation=arg.annotation)
            new_args.append(new_arg)
        else:
            # If the argument is not in the old argument list, use the new argument and annotation
            new_args.append(arg)
    
    # Assign the new argument list to the arguments of the old function AST
    old_function_ast.args.args = new_args
    return old_function_ast

test = """
def abs(n):
    \"\"\" WUT \"\"\"
    # Check if integer is negative
    if n < 0:
        # Return the opposite sign of n (i.e., multiply n by -1)
        return -n
    else:
        # Return n (which is already a positive integer or zero)
        return n
"""

test2 = """
def abs(n):
    if n < 0:
        return -n
    else:
        return n
"""

import ast

def remove_code_before_function(code):
    # Parse the code into an AST
    tree = ast.parse(code)

    # Find the position of the first function definition
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start_index = node.lineno - 1  # Subtract 1 to remove leading newline
            break
    else:
        # No function definition found, return the original code
        return code

    # Extract the code from the first function definition onwards
    lines = code.splitlines()
    return '\n'.join(lines[start_index:])

def remove_annotations(node):
    if isinstance(node, ast.AnnAssign):
        node.annotation = None
    elif isinstance(node, ast.FunctionDef):
        for arg in node.args.args:
            arg.annotation = None
        node.returns = None
            
def remove_comments(node):
    if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef) or \
       isinstance(node, ast.ClassDef) or isinstance(node, ast.Module):
        if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Str):
            node.body[0].value.s = ''
        node.body = [n for n in node.body if not isinstance(n, ast.Expr) or not isinstance(n.value, ast.Str)]
    elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Str):
        node.value.s = ''

def compare_python_code(code1, code2):
    # Parse the code into an AST
    tree1 = ast.parse(code1)
    tree2 = ast.parse(code2)

    # Remove any comments from the AST
    for node in ast.walk(tree1):
        remove_comments(node)
        remove_annotations(node)
    for node in ast.walk(tree2):
        remove_comments(node)
        remove_annotations(node)

    # Compare the two ASTs
    return ast.unparse(tree1) == ast.unparse(tree2)


def now_has_types(code1, code2):
    # Parse the code into an AST
    tree1 = ast.parse(code1)
    tree2 = ast.parse(code2)
    print(f"BEFORE: {ast.unparse(tree2)}")

    for node in ast.walk(tree2):
        remove_annotations(node)

    # Compare the two ASTs
    # Return True iff we've added types to the second.
    return ast.unparse(tree1) != ast.unparse(tree2)


def extract_function_ast(program_str, function_name):
    # Parse the program string into an AST
    program_ast = ast.parse(program_str)

    # Find the FunctionDef node corresponding to the desired function
    function_node = next((n for n in program_ast.body if isinstance(n, ast.FunctionDef) and n.name == function_name), None)

    if function_node is None:
        raise ValueError(f"No function named '{function_name}' was found")
    
    return function_node

def extract_function_source(program_str, function_name):
    return ast.unparse(extract_function_ast(program_str, function_name))

    # Parse the program string into an AST
    program_ast = ast.parse(program_str)

    # Find the FunctionDef node corresponding to the desired function
    function_node = next((n for n in program_ast.body if isinstance(n, ast.FunctionDef) and n.name == function_name), None)

    if function_node is None:
        raise ValueError(f"No function named '{function_name}' was found")

    # Convert the FunctionDef node back to source code
    return ast.unparse(function_node)


def enumerate_functions(program_str):
    # Parse the program string into an AST
    program_ast = ast.parse(program_str)

    # Find all FunctionDef nodes and extract their names
    names = [n.name for n in program_ast.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]

    return names

def replace_function(program_str, function_name, new_function_str):
    # Parse the program string into an AST
    program_ast = ast.parse(program_str)

    # Find the FunctionDef node corresponding to the desired function
    function_node = next((n for n in program_ast.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == function_name), None)

    if function_node is None:
        raise ValueError(f"No function named '{function_name}' was found")

    # Parse the new function string into an AST
    new_function_ast = extract_function_ast(new_function_str, function_name)

    # Replace the old function body with the new function body
    function_node.body = new_function_ast.body
    
    # Replace the (possibly now annotated) arguments
    update_args(function_node, new_function_ast)

    # Convert the modified AST back to source code
    return ast.unparse(program_ast)


def extract_names(ast_node):
    """Extracts all class, function, and variable names from a parsed AST node."""
    names = set()

    # Visit all the child nodes of the current node.
    for child in ast.iter_child_nodes(ast_node):

        # If the child node defines a class or function, add its name to the set.
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(child.name)

        # If the child node defines a variable, add its name to the set.
        elif isinstance(child, ast.Assign):
            for target in child.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)

        # Recursively visit the child node's children.
        names.update(extract_names(child))

    return names


def get_language_from_file_name(file_name):
    """Given a file name, extracts the extension and maps it to a programming language.

      Args:
          file_name: A string representing the name of the file.
    
      Returns:
          A string representing a programming language, or an empty string if the extension is not recognized."""
    
    ext = file_name.split(".")[-1]
    language_map = {
        "js": "JavaScript",
        "ts": "TypeScript",
        "c": "C",
        "cpp": "C++",
        "cs": "C#",
        "swift": "Swift",
        "py": "Python",
        "rs": "Rust",
        "sql": "SQL",
        "css": "CSS",
        "php": "PHP",
        "rb": "Ruby",
        "kt": "Kotlin",
        "go": "Go",
        "r": "R",
        "java": "Java",
        "h": "C",
        "hpp": "C++",
        "hxx": "C++",
    }
    if ext in language_map:
        return language_map[ext]
    else:
        return ""
    
def find_code_start(code):
    # Split the code into lines
    lines = code.split("\n")

    # Skip empty lines at the beginning
    i = 0
    while i < len(lines) and lines[i].strip() == "":
        i += 1

    # Get the first line of code
    first_line = lines[i].strip()

    # If the first line is just "```", return 3
    if first_line == "```":
        return 3

    # If the first line starts with "```" followed by a single word, return the length of the word plus 3
    if first_line.startswith("```"):
        word = first_line[3:].strip()
        if len(word) > 0 and " " not in word:
            return len(word) + 3

    # If the first line doesn't match either of the above patterns, return -1
    return -1

test = """
```python
def abs(n):
    # Check if integer is negative
    if n < 0:
        # Return the opposite sign of n (i.e., multiply n by -1)
        return -n
    else:
        # Return n (which is already a positive integer or zero)
        return n
```
"""

def commentate(filename, code, language=None):
    """
    This function takes in a string of code and an optional language parameter. If language is specified,
    the function translates each docstring and comment in the code to the specified language and includes the 
    translated text in the output. If language is not specified, the function does not include any translations
    in the output. The output text includes the original code, high-level explanatory comments, and any 
    translated text (if language is specified). 

    Args:
    code (str): A string of code.
    language (str, optional): A language code to specify the output language of docstrings and comments. 
                              Defaults to None.

    Returns:
    str: A string of the processed code.
    """
    if language:
        translate_text = f"Write each docstring and comment first in English, then add a newline and '---', and add the translation to {language}."
    else:
        translate_text = ""

    programming_language = get_language_from_file_name(filename)+ " "

    max_tries = 3

    tries = 0
    
    for func_name in enumerate_functions(code):

        while tries < max_tries:

            tries += 1
        
            print(f"  commentating {func_name} ({tries}) ...", end="", flush=True)
            the_code = extract_function_source(code, func_name)

            content = f"Rewrite the following {programming_language}code by adding high-level explanatory comments, PEP 257 docstrings, and PEP 484 style type annotations. Infer what each function does, using the names and computations as hints. If there are existing comments or types, augment them rather than replacing them. If the existing comments are inconsistent with the code, correct them. Every function argument and return value should be typed if possible. Do not change any other code. {translate_text} {the_code}"

            try:
                completion = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo", 
                    messages=[
                        {"role": "system",
                         "content" : "You are a {programming_language}programming assistant who ONLY responds with blocks of code. You never respond with text. Just code, starting with ``` and ending with ```."},
                        {"role": "user",
                         "content": content}
                    ]
                )
            except openai.error.APIError:
                print("encountered a system error, retrying.")
                continue

            c = completion

            text = c['choices'][0]['message']['content']

            first_index = find_code_start(text) # text.find("```")
            second_index = text.find("```", first_index + 1)
            if first_index == -1 or second_index == -1:
                # Assume that a code block was emitted that wasn't surrounded by ```.
                code_block = text
            else:
                code_block = text[first_index:second_index]

            if get_language_from_file_name(filename) == "Python":
                try:
                    result_ast = ast.parse(code_block)
                except:
                    # print(f"Parse failure: {code_block}")
                    print("failed (parse failure).")
                    result_ast = None

            if result_ast:
                orig_ast = ast.parse(the_code)
                if not compare_python_code(remove_code_before_function(the_code),
                                           remove_code_before_function(code_block)):
                    # if extract_names(orig_ast) != extract_names(result_ast):
                    print(f"failed: {remove_code_before_function(ast.unparse(orig_ast))} / {remove_code_before_function(ast.unparse(result_ast))}.")
                    print("failed (failed to validate).")
                    code_block = None
            else:
                code_block = None

            if code_block:
                print(f"CHECKING {code_block}")
                if not now_has_types(the_code, code_block):
                    print("Failed to add types.")
                else:
                    print(f"success! CODE BLOCK {code_block}")
                    # Successfully parsed the code. Integrate it.
                    print(f"old code: {code}")
                    code = replace_function(code, func_name, code_block)
                    print(f"new code: {code}")
                    break
        
    return code


def api_key():
    key = ""
    try:
        key = os.environ['OPENAI_API_KEY']
    except:
        pass
    return key
    
