"""
Converts AST to ASR.

This is a work in progress module, which will eventually replace analyze.py
once it reaches feature parity with it.
"""

from ..ast import ast
from ..asr import asr
from ..asr.builder import (make_translation_unit,
    translation_unit_make_module, scope_add_function, make_type_integer,
    make_type_real, type_eq, make_binop, scope_add_symbol)

from .analyze import TypeMismatch

def string_to_type(stype, kind=None):
    """
    Converts a string `stype` and a numerical `kind` to an ASR type.
    """
    if stype == "integer":
        return make_type_integer(kind)
    elif stype == "real":
        return make_type_real(kind)
    elif stype == "complex":
        raise NotImplementedError("Complex not implemented")
    elif stype == "character":
        raise NotImplementedError("Complex not implemented")
    elif stype == "logical":
        raise NotImplementedError("Complex not implemented")
    raise Exception("Unknown type")


class SymbolTableVisitor(ast.GenericASTVisitor):

    def __init__(self):
        pass

    def visit_TranslationUnit(self, node):
        self._unit = make_translation_unit()
        self._current_scope = self._unit.global_scope
        for item in node.items:
            self.visit(item)

    def visit_Module(self, node):
        self._current_module = translation_unit_make_module(self._unit,
            node.name)
        old_scope = self._current_scope
        self._current_scope = self._current_module.symtab
        self.visit_sequence(node.contains)
        self._current_scope = old_scope

    def visit_Function(self, node):
        args = [arg.arg for arg in node.args]
        if node.return_var:
            name = node.return_var.id # Name of the result(...) var
        else:
            name = node.name # Name of the function
        if node.return_type:
            type = string_to_type(node.return_type)
        else:
            # FIXME: should return None here
            #type = None
            type = make_type_integer()
        return_var = asr.Variable(name=name, type=type)
        f = scope_add_function(self._current_scope, node.name,
                args=args, return_var=return_var)

        old_scope = self._current_scope
        self._current_scope = f.symtab
        self.visit_sequence(node.decl)
        self._current_scope = old_scope

    def visit_Declaration(self, node):
        for v in node.vars:
            name = v.sym
            type = string_to_type(v.sym_type)
            dims = []
            for dim in v.dims:
                if isinstance(dim.end, ast.Num):
                    dims.append(int(dim.end.n))
                else:
                    raise NotImplementedError("Index not a number")
                if dim.start:
                    raise NotImplementedError("start index")
            #if len(dims) > 0:
            #    type = Array(type, dims)
            if name in self._current_scope.symbols:
                sym = self._current_scope.symbols[name]
            else:
                sym = asr.Variable(name=name, type=type, dummy=False)
                scope_add_symbol(self._current_scope, sym)
            assert sym.name == name
            for a in v.attrs:
                if a.name == "intent":
                    sym.intent = a.args[0].arg

class BodyVisitor(ast.GenericASTVisitor):

    def __init__(self, unit):
        self._unit = unit

    def visit_sequence(self, seq):
        r = []
        if seq is not None:
            for node in seq:
                r.append(self.visit(node))
        return r

    def visit_TranslationUnit(self, node):
        self._current_scope = self._unit.global_scope
        items = []
        for item in node.items:
            a = self.visit(item)
            if a:
                items.append(a)
        self._unit.items = items

    def visit_Module(self, node):
        old_scope = self._current_scope
        self._current_scope = old_scope.symbols[node.name].symtab

        self.visit_sequence(node.contains)

        self._current_scope = old_scope

    def visit_Function(self, node):
        old_scope = self._current_scope
        self._current_scope = old_scope.symbols[node.name].symtab
        self._current_function = old_scope.symbols[node.name]

        body = self.visit_sequence(node.body)
        self._current_function.body = body
        self.visit_sequence(node.contains)

        self._current_scope = old_scope

    def visit_Assignment(self, node):
        if isinstance(node.target, ast.Name):
            r = self._current_scope.symbols[node.target.id]
            value = self.visit(node.value)
            return asr.Assignment(r, value)
        else:
            raise NotImplementedError()

    def visit_BinOp(self, node):
        left = self.visit(node.left)
        right = self.visit(node.right)
        if isinstance(node.op, ast.Add):
            op = asr.Add()
        elif isinstance(node.op, ast.Sub):
            op = asr.Sub()
        elif isinstance(node.op, ast.Mul):
            op = asr.Mul()
        elif isinstance(node.op, ast.Div):
            op = asr.Div()
        elif isinstance(node.op, ast.Pow):
            op = asr.Pow()
        else:
            assert False
        return make_binop(left=left, op=op, right=right)

    def visit_Name(self, node):
        if not self._current_scope.resolve(node.id, False):
            raise UndeclaredVariableError("Variable '%s' not declared." \
                    % node.id)
        return self._current_scope.symbols[node.id]

def wrap_ast_translation_unit(astree):
    # Note: We wrap the `astree` into an ast.TranslationUnit. This should
    # eventually be moved into parse() itself (the rest of LFortran would
    # need to be updated).
    assert not isinstance(astree, ast.TranslationUnit)
    if isinstance(astree, list):
        items = astree
    else:
        items = [astree]
    return ast.TranslationUnit(items=items)

def ast_to_asr(astree):
    astree = wrap_ast_translation_unit(astree)
    v = SymbolTableVisitor()
    assert isinstance(astree, ast.TranslationUnit)
    v.visit(astree)
    unit = v._unit

    v = BodyVisitor(unit)
    v.visit(astree)
    return unit
