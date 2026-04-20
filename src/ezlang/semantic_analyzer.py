"""
EzLang Semantic Analyzer Module
"""

from .antlr_generated.EzLangVisitor import EzLangVisitor
from .antlr_generated.EzLangParser import EzLangParser

class Type:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"Type({self.name})"

class BasicType(Type):
    pass

class Symbol:
    def __init__(self, name, type_obj):
        self.name = name
        self.type_obj = type_obj

class SymbolTable:
    def __init__(self, parent=None):
        self.symbols = {}
        self.types = {
            "I8": BasicType("I8"),
            "I32": BasicType("I32"),
            "I64": BasicType("I64"),
            "U8": BasicType("U8"),
            "U32": BasicType("U32"),
            "U64": BasicType("U64"),
            "F32": BasicType("F32"),
            "F64": BasicType("F64"),
            "Str": BasicType("Str"),
            "Bool": BasicType("Bool"),
            "Void": BasicType("Void"),
        }
        self.parent = parent

    def define(self, name, symbol):
        self.symbols[name] = symbol

    def lookup(self, name):
        if name in self.symbols:
            return self.symbols[name]
        if self.parent:
            return self.parent.lookup(name)
        return None

    def lookup_type(self, name):
        if name in self.types:
            return self.types[name]
        if self.parent:
            return self.parent.lookup_type(name)
        return None

class SemanticAnalyzer(EzLangVisitor):
    def __init__(self, tree):
        self.tree = tree
        self.symbol_table = SymbolTable()
        self.errors = []

    def analyze(self):
        self.visit(self.tree)
        if self.errors:
            raise Exception("Semantic errors:\n" + "\n".join(self.errors))

    def visitVariableDeclaration(self, ctx: EzLangParser.VariableDeclarationContext):
        var_name = ctx.ID().getText()
        var_type = None
        
        if ctx.type_():
            var_type = self.visit(ctx.type_())
        
        # TODO: Type inference if var_type is None
        
        self.symbol_table.define(var_name, Symbol(var_name, var_type))
        return self.visitChildren(ctx)

    def visitType(self, ctx: EzLangParser.TypeContext):
        # 简单实现：只取第一个 simpleType
        if ctx.simpleType():
            return self.visit(ctx.simpleType(0))
        return None

    def visitSimpleType(self, ctx: EzLangParser.SimpleTypeContext):
        base_name = ctx.baseType().getText()
        t = self.symbol_table.lookup_type(base_name)
        if not t:
            self.errors.append(f"Undefined type: {base_name}")
            return Type(base_name)
        return t

    # 忽略不需要处理的节点或使用默认行为
    def visitProgram(self, ctx: EzLangParser.ProgramContext):
        return self.visitChildren(ctx)