"""
EzLang ANTLR4 Parse Tree → AST 转换器 (Visitor)。
将 ANTLR4 生成的 CST 转换为 compiler.ast_nodes 中定义的 AST。
"""

from __future__ import annotations

from typing import Optional

from compiler.ast_nodes import (
    Program, SourceSpan,
    # Types
    NamedType, OptionalType, ListType, UnionType, FunctionType,
    VecType, PointerType, ShapeType, ShapeField, TypeNode,
    # Expressions
    IntLiteral, FloatLiteral, StringLiteral, BoolLiteral,
    Identifier, BinaryExpr, UnaryExpr, AssignExpr, ConditionalExpr,
    MemberAccess, CallExpr, IndexExpr, PipeExpr, LambdaExpr,
    MatchExpr, MatchArm, LoopExpr, CatchExpr, AwaitExpr,
    TypeofExpr, ArrayLiteral, VecLiteral, DictLiteral, DictEntry,
    TypeAssertExpr, NamedArg, ParamNode, ExprNode,
    # Statements
    LetDecl, ConstDecl, StaticDecl, StructDef, StructField,
    TypeDef, DeclareStmt, ImportStmt, ImportItem, ExportStmt,
    ReturnStmt, ThrowStmt, BreakStmt, ContinueStmt,
    ExprStmt, BlockStmt, StmtNode,
)

# ANTLR4 generated imports — 编译文法后可用
try:
    from compiler.generated.EzLangParser import EzLangParser
    from compiler.generated.EzLangVisitor import EzLangVisitor
except ImportError:
    # 文法尚未生成时，提供 fallback 基类
    class EzLangParser:
        pass
    class EzLangVisitor:
        def visit(self, ctx): pass
        def visitChildren(self, ctx): pass


def _span(ctx) -> SourceSpan:
    """从 ANTLR4 context 提取源码位置。"""
    if ctx is None:
        return SourceSpan()
    start = ctx.start if hasattr(ctx, 'start') else None
    stop = ctx.stop if hasattr(ctx, 'stop') else None
    return SourceSpan(
        start_line=start.line if start else 0,
        start_col=start.column if start else 0,
        end_line=stop.line if stop else 0,
        end_col=stop.column if stop else 0,
    )


class ASTBuilder(EzLangVisitor):
    """
    将 ANTLR4 parse tree 转换为 EzLang AST。
    继承 EzLangVisitor，重写每个语法规则的 visit 方法。
    """

    def __init__(self, file: str = "<stdin>"):
        self._file = file

    def _make_span(self, ctx) -> SourceSpan:
        span = _span(ctx)
        span.file = self._file
        return span

    # ======================== Program ========================

    def visitProgram(self, ctx):
        stmts = []
        for child in ctx.topLevelStatement():
            stmt = self.visit(child)
            if stmt is not None:
                stmts.append(stmt)
        return Program(statements=stmts, span=self._make_span(ctx))

    def visitTopLevelStatement(self, ctx):
        return self.visit(ctx.statement())

    # ======================== Statements ========================

    def visitStatement(self, ctx):
        return self.visitChildren(ctx)

    def visitLetDecl(self, ctx):
        name = ctx.IDENT().getText()
        type_node = self.visit(ctx.typeExpr()) if ctx.typeExpr() else None
        value = self.visit(ctx.expression())
        decorator = ctx.decorator().IDENT().getText() if ctx.decorator() else None
        return LetDecl(
            name=name, type=type_node, value=value,
            decorator=decorator, span=self._make_span(ctx)
        )

    def visitConstDecl(self, ctx):
        name = ctx.IDENT().getText()
        type_node = self.visit(ctx.typeExpr()) if ctx.typeExpr() else None
        value = self.visit(ctx.expression())
        is_async = ctx.ASYNC() is not None
        decorator = ctx.decorator().IDENT().getText() if ctx.decorator() else None
        return ConstDecl(
            name=name, type=type_node, value=value,
            is_async=is_async, decorator=decorator,
            span=self._make_span(ctx)
        )

    def visitStaticDecl(self, ctx):
        name = ctx.IDENT().getText()
        type_node = self.visit(ctx.typeExpr()) if ctx.typeExpr() else None
        value = self.visit(ctx.expression())
        return StaticDecl(name=name, type=type_node, value=value, span=self._make_span(ctx))

    def visitStructDef(self, ctx):
        name = ctx.IDENT().getText()
        type_params = []
        if ctx.typeParams():
            type_params = [t.getText() for t in ctx.typeParams().IDENT()]
        fields = [self.visit(m) for m in ctx.structMember()]
        return StructDef(name=name, type_params=type_params, fields=fields, span=self._make_span(ctx))

    def visitStructMember(self, ctx):
        if ctx.DOTDOTDOT():
            return StructField(
                is_spread=True,
                spread_name=ctx.IDENT().getText(),
                span=self._make_span(ctx)
            )
        ident = ctx.IDENT().getText()
        if ctx.typeExpr():
            type_node = self.visit(ctx.typeExpr())
            default = self.visit(ctx.expression()) if ctx.expression() else None
            return StructField(name=ident, type=type_node, default=default, span=self._make_span(ctx))
        else:
            value = self.visit(ctx.expression())
            return StructField(name=ident, default=value, span=self._make_span(ctx))

    def visitTypeDef(self, ctx):
        name = ctx.IDENT().getText()
        type_params = []
        if ctx.typeParams():
            type_params = [t.getText() for t in ctx.typeParams().IDENT()]
        if ctx.shapeType():
            value = self.visit(ctx.shapeType())
        else:
            value = self.visit(ctx.typeExpr())
        return TypeDef(name=name, type_params=type_params, value=value, span=self._make_span(ctx))

    def visitShapeType(self, ctx):
        fields = [self.visit(m) for m in ctx.shapeMember()]
        return ShapeType(fields=fields, span=self._make_span(ctx))

    def visitShapeMember(self, ctx):
        if ctx.DOTDOTDOT():
            return ShapeField(name=ctx.IDENT().getText(), is_spread=True, span=self._make_span(ctx))
        idents = ctx.IDENT()
        if ctx.LBRACKET():
            # [key: KeyType]: ValueType
            return ShapeField(
                name=idents[0].getText(),
                is_dynamic=True,
                key_type=self.visit(ctx.typeExpr(0)),
                type=self.visit(ctx.typeExpr(1)),
                span=self._make_span(ctx)
            )
        return ShapeField(
            name=idents[0].getText(),
            type=self.visit(ctx.typeExpr(0)),
            span=self._make_span(ctx)
        )

    def visitDeclareStmt(self, ctx):
        name = ctx.IDENT().getText()
        type_node = self.visit(ctx.typeExpr())
        return DeclareStmt(name=name, type=type_node, span=self._make_span(ctx))

    def visitImportStmt(self, ctx):
        path = ctx.STRING().getText().strip('"')
        items = [self.visit(i) for i in ctx.importItem()]
        return ImportStmt(path=path, items=items, span=self._make_span(ctx))

    def visitImportItem(self, ctx):
        idents = ctx.IDENT()
        name = idents[0].getText()
        alias = idents[1].getText() if len(idents) > 1 else None
        return ImportItem(name=name, alias=alias, span=self._make_span(ctx))

    def visitExportStmt(self, ctx):
        if ctx.letDecl():
            decl = self.visit(ctx.letDecl())
        elif ctx.constDecl():
            decl = self.visit(ctx.constDecl())
        else:
            decl = self.visit(ctx.staticDecl())
        return ExportStmt(declaration=decl, span=self._make_span(ctx))

    def visitReturnStmt(self, ctx):
        value = self.visit(ctx.expression()) if ctx.expression() else None
        return ReturnStmt(value=value, span=self._make_span(ctx))

    def visitThrowStmt(self, ctx):
        return ThrowStmt(value=self.visit(ctx.expression()), span=self._make_span(ctx))

    def visitBreakStmt(self, ctx):
        return BreakStmt(span=self._make_span(ctx))

    def visitContinueStmt(self, ctx):
        return ContinueStmt(span=self._make_span(ctx))

    def visitExprStmt(self, ctx):
        return ExprStmt(expr=self.visit(ctx.expression()), span=self._make_span(ctx))

    def visitLoopStmt(self, ctx):
        # loopStmt just wraps loopExpr, which returns a LoopExpr (ExprNode)
        return ExprStmt(expr=self.visit(ctx.loopExpr()), span=self._make_span(ctx))

    def visitMatchStmt(self, ctx):
        # matchStmt just wraps matchExpr, which returns a MatchExpr (ExprNode)
        return ExprStmt(expr=self.visit(ctx.matchExpr()), span=self._make_span(ctx))

    def visitCondBlockStmt(self, ctx):
        # condBlockStmt is the statement form of a conditional block
        condition = self.visit(ctx.pipeExpr())
        blocks = ctx.block()
        then_block = self.visit(blocks[0])
        else_part = None
        if ctx.conditionalExpr():
            else_part = self.visit(ctx.conditionalExpr())
        elif len(blocks) > 1:
            else_part = self.visit(blocks[1])
        
        return ExprStmt(expr=ConditionalExpr(
            condition=condition, then_expr=then_block,
            else_expr=else_part, span=self._make_span(ctx)
        ), span=self._make_span(ctx))

    # ======================== Expressions ========================

    def visitExpression(self, ctx):
        return self.visit(ctx.assignExpr())

    def visitAssignExpr(self, ctx):
        if ctx.assignOp():
            target = self.visit(ctx.conditionalExpr())
            value = self.visit(ctx.assignExpr())
            op = ctx.assignOp().getText()
            return AssignExpr(op=op, target=target, value=value, span=self._make_span(ctx))
        return self.visit(ctx.conditionalExpr())

    def visitConditionalExpr(self, ctx):
        if ctx.QUESTION():
            condition = self.visit(ctx.pipeExpr())
            # 判断各种条件表达式形式
            if ctx.block():
                blocks = ctx.block()
                then_block = self.visit(blocks[0])
                else_part = None
                if ctx.conditionalExpr():
                    else_part = self.visit(ctx.conditionalExpr())
                elif len(blocks) > 1:
                    else_part = self.visit(blocks[1])
                return ConditionalExpr(
                    condition=condition, then_expr=then_block,
                    else_expr=else_part, span=self._make_span(ctx)
                )
            elif ctx.BREAK():
                return ConditionalExpr(
                    condition=condition,
                    then_expr=BreakStmt(span=self._make_span(ctx)),
                    span=self._make_span(ctx)
                )
            elif ctx.CONTINUE():
                return ConditionalExpr(
                    condition=condition,
                    then_expr=ContinueStmt(span=self._make_span(ctx)),
                    span=self._make_span(ctx)
                )
            else:
                exprs = ctx.expression()
                if not exprs:
                    # 这不应该发生，除非文法规则有误
                    return self.visit(ctx.pipeExpr())
                then_expr = self.visit(exprs[0])
                else_expr = self.visit(exprs[1]) if len(exprs) > 1 else None
                return ConditionalExpr(
                    condition=condition, then_expr=then_expr,
                    else_expr=else_expr, span=self._make_span(ctx)
                )
        return self.visit(ctx.pipeExpr())

    def visitPipeExpr(self, ctx):
        expr = self.visit(ctx.orExpr())
        idents = ctx.IDENT()
        for i, ident in enumerate(idents):
            args = []
            if ctx.namedArgList(i):
                args = self._visit_named_arg_list(ctx.namedArgList(i))
            expr = PipeExpr(value=expr, func_name=ident.getText(), args=args, span=self._make_span(ctx))
        return expr

    def _visit_binary_chain(self, ctx, child_method: str, ops):
        """通用的二元运算链处理。"""
        children = getattr(ctx, child_method)()
        result = self.visit(children[0])
        for i in range(1, len(children)):
            op_token = ops[i - 1] if isinstance(ops, list) else ctx.getChild(2 * i - 1).getText()
            right = self.visit(children[i])
            result = BinaryExpr(op=op_token, left=result, right=right, span=self._make_span(ctx))
        return result

    def visitOrExpr(self, ctx):
        children = ctx.andExpr()
        result = self.visit(children[0])
        for i in range(1, len(children)):
            right = self.visit(children[i])
            result = BinaryExpr(op="||", left=result, right=right, span=self._make_span(ctx))
        return result

    def visitAndExpr(self, ctx):
        children = ctx.bitOrExpr()
        result = self.visit(children[0])
        for i in range(1, len(children)):
            right = self.visit(children[i])
            result = BinaryExpr(op="&&", left=result, right=right, span=self._make_span(ctx))
        return result

    def visitBitOrExpr(self, ctx):
        children = ctx.bitXorExpr()
        result = self.visit(children[0])
        for i in range(1, len(children)):
            right = self.visit(children[i])
            result = BinaryExpr(op="|", left=result, right=right, span=self._make_span(ctx))
        return result

    def visitBitXorExpr(self, ctx):
        children = ctx.bitAndExpr()
        result = self.visit(children[0])
        for i in range(1, len(children)):
            right = self.visit(children[i])
            result = BinaryExpr(op="^", left=result, right=right, span=self._make_span(ctx))
        return result

    def visitBitAndExpr(self, ctx):
        children = ctx.eqExpr()
        result = self.visit(children[0])
        for i in range(1, len(children)):
            right = self.visit(children[i])
            result = BinaryExpr(op="&", left=result, right=right, span=self._make_span(ctx))
        return result

    def visitEqExpr(self, ctx):
        children = ctx.compExpr()
        result = self.visit(children[0])
        for i in range(1, len(children)):
            op = ctx.getChild(2 * i - 1).getText()
            right = self.visit(children[i])
            result = BinaryExpr(op=op, left=result, right=right, span=self._make_span(ctx))
        return result

    def visitCompExpr(self, ctx):
        children = ctx.shiftExpr()
        result = self.visit(children[0])
        for i in range(1, len(children)):
            op = ctx.getChild(2 * i - 1).getText()
            right = self.visit(children[i])
            result = BinaryExpr(op=op, left=result, right=right, span=self._make_span(ctx))
        return result

    def visitShiftExpr(self, ctx):
        children = ctx.addExpr()
        result = self.visit(children[0])
        for i in range(1, len(children)):
            op = ctx.getChild(2 * i - 1).getText()
            right = self.visit(children[i])
            result = BinaryExpr(op=op, left=result, right=right, span=self._make_span(ctx))
        return result

    def visitAddExpr(self, ctx):
        children = ctx.mulExpr()
        result = self.visit(children[0])
        for i in range(1, len(children)):
            op = ctx.getChild(2 * i - 1).getText()
            right = self.visit(children[i])
            result = BinaryExpr(op=op, left=result, right=right, span=self._make_span(ctx))
        return result

    def visitMulExpr(self, ctx):
        children = ctx.unaryExpr()
        result = self.visit(children[0])
        for i in range(1, len(children)):
            op = ctx.getChild(2 * i - 1).getText()
            right = self.visit(children[i])
            result = BinaryExpr(op=op, left=result, right=right, span=self._make_span(ctx))
        return result

    def visitUnaryExpr(self, ctx):
        if ctx.BANG():
            return UnaryExpr(op="!", operand=self.visit(ctx.unaryExpr()), span=self._make_span(ctx))
        if ctx.MINUS():
            return UnaryExpr(op="-", operand=self.visit(ctx.unaryExpr()), span=self._make_span(ctx))
        return self.visit(ctx.postfixExpr())

    def visitPostfixExpr(self, ctx):
        result = self.visit(ctx.primaryExpr())
        for p in ctx.postfix():
            result = self._apply_postfix(result, p)
        return result

    def _apply_postfix(self, expr: ExprNode, ctx) -> ExprNode:
        if ctx.DOT():
            return MemberAccess(object=expr, member=ctx.IDENT().getText(), span=self._make_span(ctx))
        if ctx.LPAREN() is not None:
            args = self._visit_named_arg_list(ctx.namedArgList()) if ctx.namedArgList() else []
            return CallExpr(callee=expr, args=args, span=self._make_span(ctx))
        if ctx.LBRACKET():
            index = self.visit(ctx.expression())
            return IndexExpr(object=expr, index=index, span=self._make_span(ctx))
        return expr

    def _visit_named_arg_list(self, ctx) -> list[NamedArg]:
        return [self.visit(a) for a in ctx.namedArg()]

    def visitNamedArg(self, ctx):
        if ctx.DOTDOTDOT():
            return NamedArg(is_spread=True, value=self.visit(ctx.expression()), span=self._make_span(ctx))
        name = ctx.IDENT().getText()
        if ctx.QUESTION():
            return NamedArg(name=name, is_placeholder=True, span=self._make_span(ctx))
        return NamedArg(name=name, value=self.visit(ctx.expression()), span=self._make_span(ctx))

    def visitPrimaryExpr(self, ctx):
        if ctx.INT_LIT():
            text = ctx.INT_LIT().getText()
            if text.startswith("0x"):
                value = int(text, 16)
            elif text.startswith("0b"):
                value = int(text, 2)
            else:
                value = int(text)
            return IntLiteral(value=value, span=self._make_span(ctx))

        if ctx.FLOAT_LIT():
            return FloatLiteral(value=float(ctx.FLOAT_LIT().getText()), span=self._make_span(ctx))

        if ctx.STRING():
            raw = ctx.STRING().getText()
            return StringLiteral(value=raw[1:-1], span=self._make_span(ctx))

        if ctx.BOOL_LIT():
            return BoolLiteral(value=ctx.BOOL_LIT().getText() == "true", span=self._make_span(ctx))

        if ctx.IDENT():
            return Identifier(name=ctx.IDENT().getText(), span=self._make_span(ctx))

        if ctx.LPAREN():
            return self.visit(ctx.expression())

        if ctx.block():
            return self.visit(ctx.block())

        if ctx.lambdaExpr():
            return self.visit(ctx.lambdaExpr())

        if ctx.matchExpr():
            return self.visit(ctx.matchExpr())

        if ctx.loopExpr():
            return self.visit(ctx.loopExpr())

        if ctx.catchExpr():
            return self.visit(ctx.catchExpr())

        if ctx.arrayLiteral():
            return self.visit(ctx.arrayLiteral())

        if ctx.vecLiteral():
            return self.visit(ctx.vecLiteral())

        if ctx.dictLiteral():
            return self.visit(ctx.dictLiteral())

        if ctx.typeofExpr():
            return self.visit(ctx.typeofExpr())

        if ctx.AWAIT():
            return AwaitExpr(expr=self.visit(ctx.expression()), span=self._make_span(ctx))

        return ExprNode(span=self._make_span(ctx))

    def visitLambdaExpr(self, ctx):
        type_params = []
        if ctx.typeParams():
            type_params = [t.getText() for t in ctx.typeParams().IDENT()]
        params = [self.visit(p) for p in ctx.paramList().param()] if ctx.paramList() else []
        ret_type = self.visit(ctx.typeExpr()) if ctx.typeExpr() else None
        body = self.visit(ctx.block()) if ctx.block() else self.visit(ctx.expression())
        return LambdaExpr(
            type_params=type_params, params=params,
            return_type=ret_type, body=body,
            span=self._make_span(ctx)
        )

    def visitParam(self, ctx):
        name = ctx.IDENT().getText()
        type_node = self.visit(ctx.typeExpr())
        default = self.visit(ctx.expression()) if ctx.expression() else None
        return ParamNode(name=name, type=type_node, default=default, span=self._make_span(ctx))

    def visitBlock(self, ctx):
        stmts = [self.visit(s) for s in ctx.statement()]
        return BlockStmt(statements=stmts, span=self._make_span(ctx))

    def visitMatchExpr(self, ctx):
        arms = [self.visit(a) for a in ctx.matchArm()]
        return MatchExpr(arms=arms, span=self._make_span(ctx))

    def visitMatchArm(self, ctx):
        condition = self.visit(ctx.expression(0) if ctx.expression() else ctx.LPAREN())
        if ctx.block():
            body = self.visit(ctx.block())
        else:
            # 第二个 expression 是 body
            exprs = ctx.expression()
            body = self.visit(exprs[1]) if len(exprs) > 1 else self.visit(exprs[0])
        return MatchArm(condition=condition, body=body, span=self._make_span(ctx))

    def visitLoopExpr(self, ctx):
        if ctx.IDENT():
            var = ctx.IDENT().getText()
            exprs = ctx.expression()
            start = self.visit(exprs[0])
            end = self.visit(exprs[1])
            body = self.visit(ctx.block())
            return LoopExpr(var=var, start=start, end=end, body=body, span=self._make_span(ctx))
        return LoopExpr(body=self.visit(ctx.block()), span=self._make_span(ctx))

    def visitCatchExpr(self, ctx):
        return CatchExpr(body=self.visit(ctx.block()), span=self._make_span(ctx))

    def visitArrayLiteral(self, ctx):
        elements = [self.visit(e) for e in ctx.expression()]
        return ArrayLiteral(elements=elements, span=self._make_span(ctx))

    def visitVecLiteral(self, ctx):
        elements = [self.visit(e) for e in ctx.expression()]
        return VecLiteral(elements=elements, span=self._make_span(ctx))

    def visitDictLiteral(self, ctx):
        entries = [self.visit(e) for e in ctx.dictEntry()]
        return DictLiteral(entries=entries, span=self._make_span(ctx))

    def visitDictEntry(self, ctx):
        key = ctx.IDENT().getText()
        type_node = self.visit(ctx.typeExpr()) if ctx.typeExpr() else None
        value = self.visit(ctx.expression())
        return DictEntry(key=key, type=type_node, value=value, span=self._make_span(ctx))

    def visitTypeofExpr(self, ctx):
        return TypeofExpr(expr=self.visit(ctx.expression()), span=self._make_span(ctx))

    # ======================== Type Expressions ========================

    def visitTypeExpr(self, ctx):
        return self.visit(ctx.unionType())

    def visitUnionType(self, ctx):
        types = [self.visit(t) for t in ctx.optionalType()]
        if len(types) == 1:
            return types[0]
        return UnionType(types=types, span=self._make_span(ctx))

    def visitOptionalType(self, ctx):
        inner = self.visit(ctx.arrayType())
        if ctx.QUESTION():
            return OptionalType(inner=inner, span=self._make_span(ctx))
        return inner

    def visitArrayType(self, ctx):
        inner = self.visit(ctx.atomicType())
        if ctx.LBRACKET():
            return ListType(element=inner, span=self._make_span(ctx))
        return inner

    def visitAtomicType(self, ctx):
        if ctx.IDENT():
            name = ctx.IDENT().getText()
            type_args = []
            if ctx.typeArgs():
                type_args = [self.visit(t) for t in ctx.typeArgs().typeExpr()]
            return NamedType(name=name, type_args=type_args, span=self._make_span(ctx))

        if ctx.VEC():
            elem = self.visit(ctx.typeExpr())
            count = int(ctx.INT_LIT().getText())
            return VecType(element=elem, count=count, span=self._make_span(ctx))

        if ctx.LPAREN() is not None and ctx.FAT_ARROW():
            params = [self.visit(p) for p in ctx.paramTypeList().paramType()] if ctx.paramTypeList() else []
            ret = self.visit(ctx.typeExpr())
            return FunctionType(params=params, return_type=ret, span=self._make_span(ctx))

        if ctx.STAR():
            return PointerType(pointee=ctx.IDENT().getText(), span=self._make_span(ctx))

        if ctx.shapeType():
            return self.visit(ctx.shapeType())

        return TypeNode(span=self._make_span(ctx))

    def visitParamType(self, ctx):
        name = ctx.IDENT().getText()
        type_node = self.visit(ctx.typeExpr())
        return ParamNode(name=name, type=type_node, span=self._make_span(ctx))
