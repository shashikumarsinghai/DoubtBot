import ast

# ================================
# Calculator
# ================================

def calculate_expression(expression):
    try:
        tree = ast.parse(expression, mode="eval")

        def evaluate(node):
            if isinstance(node, ast.Expression):
                return evaluate(node.body)

            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                return node.value

            if isinstance(node, ast.BinOp):
                left = evaluate(node.left)
                right = evaluate(node.right)

                if isinstance(node.op, ast.Add):
                    return left + right

                if isinstance(node.op, ast.Sub):
                    return left - right

                if isinstance(node.op, ast.Mult):
                    return left * right

                if isinstance(node.op, ast.Div):
                    return left / right

                if isinstance(node.op, ast.Mod):
                    return left % right

                if isinstance(node.op, ast.Pow):
                    return left ** right

            if isinstance(node, ast.UnaryOp):
                value = evaluate(node.operand)

                if isinstance(node.op, ast.USub):
                    return -value

                if isinstance(node.op, ast.UAdd):
                    return value

            raise ValueError("Unsupported expression")

        return evaluate(tree)

    except Exception:
        return "Invalid mathematical expression"