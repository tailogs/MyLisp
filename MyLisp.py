import math
import operator as op
from functools import reduce

# Парсер
def tokenize(chars: str) -> list:
    "Преобразует строку в список токенов, игнорируя комментарии Lisp."
    tokens = []
    while chars:
        if chars[0] == ';':  # Если строка начинается с ';', игнорируем ее как комментарий
            end_index = chars.find('\n')
            if end_index == -1:
                break  # Если до конца строки нет символа перевода строки, выходим
            chars = chars[end_index + 1:]  # Продолжаем с конца комментария
        elif chars[0] in '()':
            tokens.append(chars[0])
            chars = chars[1:]
        elif chars[0].isspace():
            chars = chars[1:]
        else:
            match = ''
            while chars and not chars[0].isspace() and chars[0] not in '();':
                match += chars[0]
                chars = chars[1:]
            tokens.append(match)
    return tokens

def parse(tokens: list):
    "Рекурсивно разбирает список токенов в вложенные списки, с учетом ошибок исходного кода."
    def parse_rec(tokens, line_number):
        if len(tokens) == 0:
            raise SyntaxError(f"unexpected EOF on line {line_number}")
        token = tokens.pop(0)
        if token == '(':
            L = []
            while tokens:
                if tokens[0] == ')':
                    tokens.pop(0)  # pop off ')'
                    return L
                else:
                    try:
                        L.append(parse_rec(tokens, line_number))
                    except SyntaxError as e:
                        raise SyntaxError(f"{e}")
            raise SyntaxError(f"unexpected EOF on line {line_number}")
        elif token == ')':
            raise SyntaxError(f"unexpected ) on line {line_number}")
        else:
            return atom(token, line_number)

    def atom(token: str, line_number):
        "Преобразует строку токена в число (int или float) или символ."
        try:
            return int(token)
        except ValueError:
            try:
                return float(token)
            except ValueError:
                return str(token)

    expressions = []
    line_number = 1
    while tokens:
        try:
            expressions.append(parse_rec(tokens, line_number))
            line_number += 1
        except SyntaxError as e:
            raise SyntaxError(f"{e} in '{' '.join(tokens)}'")
    return expressions, line_number

def read_from_string(input: str):
    "Читает строку и возвращает соответствующее выражение Lisp."
    return parse(tokenize(input))

# Анализатор
class Env(dict):
    "Окружение с некоторыми встроенными функциями."
    def __init__(self, params=(), args=(), outer=None):
        self.update(zip(params, args))
        self.outer = outer

    def find(self, var):
        "Находит самое внутреннее окружение, в котором определена переменная."
        return self if (var in self) else self.outer.find(var) if self.outer else None

def standard_env():
    "Стандартное окружение со встроенными функциями."
    env = Env()
    env.update(vars(math))  # все математические функции из модуля math
    env.update({
        '+': lambda *args: reduce(op.add, args),
        '-': lambda x, *y: x if not y else x - sum(y),
        '*': lambda *args: reduce(op.mul, args),
        '/': lambda x, *y: x if not y else reduce(op.truediv, y, x),
        '>': op.gt, '<': op.lt, '>=': op.ge, '<=': op.le, '=': op.eq,
        'abs': abs,
        'append': op.add,
        'begin': lambda *x: x[-1],
        'car': lambda x: x[0],
        'cdr': lambda x: x[1:],
        'cons': lambda x, y: [x] + y,
        'eq?': op.is_,
        'expt': pow,
        'equal?': op.eq,
        'length': len,
        'list': lambda *x: list(x),
        'list?': lambda x: isinstance(x, list),
        'map': lambda *args: list(map(*args)),
        'max': max,
        'min': min,
        'not': op.not_,
        'null?': lambda x: x == [],
        'number?': lambda x: isinstance(x, (int, float)),
        'procedure?': callable,
        'round': round,
        'symbol?': lambda x: isinstance(x, str),
    })
    return env

global_env = standard_env()

def evaluate(x, env=global_env):
    "Оценка выражения в окружении."
    if isinstance(x, str):       # переменная
        val = env.find(x)
        if val is None:
            raise NameError(f"Variable '{x}' is not defined.")
        return val[x]
    elif not isinstance(x, list):  # константа
        return x
    op, *args = x
    if op == 'quote':            # (quote exp)
        return args[0]
    elif op == 'if':             # (if test conseq alt)
        (test, conseq, alt) = args
        exp = (conseq if evaluate(test, env) else alt)
        return evaluate(exp, env)
    elif op == 'define':         # (define var exp)
        (var, exp) = args
        env[var] = evaluate(exp, env)
    elif op == 'set!':           # (set! var exp)
        (var, exp) = args
        if env.find(var):
            env.find(var)[var] = evaluate(exp, env)
        else:
            raise NameError(f"Variable '{var}' is not defined.")
    elif op == 'lambda':         # (lambda (var*) exp)
        (vars, exp) = args
        return lambda *args: evaluate(exp, Env(vars, args, env))
    else:                        # (proc exp*)
        proc = evaluate(op, env)
        vals = [evaluate(arg, env) for arg in args]
        return proc(*vals)

# Виртуальная машина
def run_code(code: str):
    "Запускает многострочный блок кода Lisp построчно."
    lines = code.strip().splitlines()
    tokens = tokenize(code)
    line_number = 1
    while tokens:
        try:
            expr, line_number = parse(tokens)
            for exp in expr:
                val = evaluate(exp)
                if val is not None:
                    print(lisp_str(val))
        except SyntaxError as e:
            # Определяем физическую строку и позицию символа ошибки
            line_pos = e.args[1]
            if line_pos <= 0:
                error_msg = f"SyntaxError at line {line_number}: {e.args[0]}"
            else:
                physical_line = lines[line_number - 1]
                error_msg = f"SyntaxError at line {line_number}, position {line_pos}: {e.args[0]}\n"
                error_msg += physical_line + '\n' + ' ' * (line_pos - 1) + '^'
            
            # Пытаемся определить символ, вызвавший ошибку
            if len(e.args) > 2 and isinstance(e.args[2], str):
                symbol_pos = e.args[2]
                error_msg += f" and symbol {symbol_pos}: {e.args[2]}\n"
                error_msg += ' ' * (symbol_pos - 1) + '^'
            
            print(error_msg)
            break
        except NameError as e:
            print(f"Error at line {line_number}: {e}")
            break
        except Exception as e:
            print(f"Error at line {line_number}: {e}")
            break
        line_number += 1

def lisp_str(exp):
    "Преобразует Python-объекты в строки Lisp."
    if isinstance(exp, list):
        return '(' + ' '.join(map(lisp_str, exp)) + ')'
    else:
        return str(exp)

if __name__ == '__main__':
    code = """
    (define factorial
        (lambda (n)
            (if (<= n 1)
                1
                (* n (factorial (- n 1))))))
    (factorial 5)
    ; Определение функции квадрат
    (define square 
        (lambda (n) (* n n)))
    (square 5)
    """
    run_code(code)
