"""AST Builder visitor for EzLang parse tree."""

from antlr4 import ParserRuleContext

try:
    from .EzLangVisitor import EzLangVisitor
    from .EzLangParser import EzLangParser
except ImportError:
    # Fallback if parser hasn't been generated yet
    pass

from ast import (
    ASTNode, Module, TypeNode, BaseType, OptionalType, UnionType,
    ArrayType, VecType, GenericType, FunctionType, TypeofType,
    Expr, LiteralExpr, IdentifierExpr, UnaryExpr, BinaryExpr,
    ConditionalExpr, MemberAccessExpr, CallExpr, IndexExpr,
    TypeAssertionExpr, OptionalUnwrapExpr, PipelineExpr,
    StructLiteralExpr, ArrayLiteralExpr, VecLiteralExpr,
    FunctionLiteralExpr, Param, BlockExpr, FlowExpr,
    MatchExpr, MatchClause, CatchExpr, LoopExpr, IfLikeExpr,
    Stmt, VariableDeclStmt, StructDeclStmt, StructField,
    StructMethod, StructSpread, TypeAliasDeclStmt, TypeShape,
    TypeShapeField, TypeShapeSpread, FunctionDeclStmt,
    ImportDeclStmt, ExportDeclStmt, ExternDeclStmt,
    DeclareDeclStmt, ExprStmt, AssignmentStmt, ReturnStmt,
    BreakStmt, ContinueStmt, ThrowStmt
)


class ASTBuilder(EzLangVisitor):
    """Converts ANTLR parse tree to AST."""

    def visitChildren(self, node):
        result = default_result()
        n = node.getChildCount()
        for i in range(n):
            child = node.getChild(i)
            child_result = child.accept(self)
            result = aggregate_result(result, child_result)
        return result

    def defaultResult(self):
        return None

    def aggregateResult(self, aggregate, nextResult):
        return nextResult if nextResult is not None else aggregate

    # === Compilation Unit ===

    def visitCompilationUnit(self, ctx: EzLangParser.CompilationUnitContext):
        stmts = []
        for child in ctx.children[:-1]:  # exclude EOF
            result = child.accept(self)
            if isinstance(result, Stmt):
                stmts.append(result)
        return Module(statements=stmts)

    # === Declarations ===

    def visitVariableDecl(self, ctx: EzLangParser.VariableDeclContext):
        kind = ctx.getChild(0).getText()
        name = ctx.IDENTIFIER().getText()
        type_ = ctx.type_().accept(self) if ctx.type_() else None
        expr = ctx.expression().accept(self)
        return VariableDeclStmt(
            kind=kind,
            name=name,
            type_=type_,
            initializer=expr,
            **self._pos(ctx)
        )

    def visitStructDecl(self, ctx: EzLangParser.StructDeclContext):
        name = ctx.IDENTIFIER().getText()
        generic_params = self._visit_generic_params(ctx.genericParams())
        members = [m.accept(self) for m in ctx.structMember()]
        return StructDeclStmt(
            name=name,
            generic_params=generic_params,
            members=members,
            **self._pos(ctx)
        )

    def visitStructSpread(self, ctx: EzLangParser.StructSpreadContext):
        base_type = ctx.type_().accept(self)
        return StructSpread(base_type=base_type, **self._pos(ctx))

    def visitStructField(self, ctx: EzLangParser.StructFieldContext):
        name = ctx.IDENTIFIER().getText()
        type_ = ctx.type_().accept(self)
        default = ctx.expression().accept(self) if ctx.expression() else None
        return StructField(
            name=name,
            type_=type_,
            default_value=default,
            **self._pos(ctx)
        )

    def visitStructMethod(self, ctx: EzLangParser.StructMethodContext):
        name = ctx.IDENTIFIER().getText()
        func = ctx.functionLiteral().accept(self)
        return StructMethod(name=name, function=func, **self._pos(ctx))

    def visitTypeAliasDecl(self, ctx: EzLangParser.TypeAliasDeclContext):
        name = ctx.IDENTIFIER().getText()
        generic_params = self._visit_generic_params(ctx.genericParams())
        shape = ctx.typeShape().accept(self)
        return TypeAliasDeclStmt(
            name=name,
            generic_params=generic_params,
            shape=shape,
            **self._pos(ctx)
        )

    def visitTypeShape(self, ctx: EzLangParser.TypeShapeContext):
        members = []
        for m in ctx.typeShapeMember():
            members.append(m.accept(self))
        for s in ctx.typeShapeSpread():
            members.append(s.accept(self))
        return TypeShape(members=members, **self._pos(ctx))

    def visitTypeShapeMember(self, ctx: EzLangParser.TypeShapeMemberContext):
        if ctx.IDENTIFIER():
            name = ctx.IDENTIFIER().getText()
            is_dynamic = False
        else:
            name = ctx.IDENTIFIER(0).getText()
            is_dynamic = True
        type_ = ctx.type_().accept(self)
        return TypeShapeField(
            name=name,
            type_=type_,
            is_dynamic_key=is_dynamic,
            **self._pos(ctx)
        )

    def visitTypeShapeSpread(self, ctx: EzLangParser.TypeShapeSpreadContext):
        base_type = ctx.type_().accept(self)
        return TypeShapeSpread(base_type=base_type, **self._pos(ctx))

    def visitFunctionDecl(self, ctx: EzLangParser.FunctionDeclContext):
        kind = ctx.getChild(0).getText()
        name = ctx.IDENTIFIER().getText()
        generic_params = self._visit_generic_params(ctx.genericParams())
        func = ctx.functionLiteral().accept(self)
        return FunctionDeclStmt(
            kind=kind,
            name=name,
            generic_params=generic_params,
            function=func,
            **self._pos(ctx)
        )

    def visitImportDecl(self, ctx: EzLangParser.ImportDeclContext):
        path = ctx.STRING_LITERAL().getText()[1:-1]  # strip quotes
        imports = {}
        if ctx.importSpecList():
            for spec in ctx.importSpecList().importSpec():
                name = spec.IDENTIFIER(0).getText()
                alias = spec.IDENTIFIER(1).getText() if spec.IDENTIFIER(1) else name
                imports[name] = alias
        return ImportDeclStmt(path=path, imports=imports, **self._pos(ctx))

    def visitExportDecl(self, ctx: EzLangParser.ExportDeclContext):
        decl = ctx.getChild(1).accept(self)
        return ExportDeclStmt(declaration=decl, **self._pos(ctx))

    def visitExternDecl(self, ctx: EzLangParser.ExternDeclContext):
        path = ctx.STRING_LITERAL().getText()[1:-1]
        target = ctx.targetPlatform().getText() if ctx.targetPlatform() else None
        return ExternDeclStmt(path=path, target=target, **self._pos(ctx))

    def visitDeclareDecl(self, ctx: EzLangParser.DeclareDeclContext):
        kind = ctx.getChild(1).getText()
        name = ctx.IDENTIFIER().getText()
        type_ = ctx.type_().accept(self)
        return DeclareDeclStmt(
            kind=kind,
            name=name,
            type_=type_,
            **self._pos(ctx)
        )

    # === Types ===

    def visitOptionalType(self, ctx: EzLangParser.OptionalTypeContext):
        base = ctx.type_().accept(self)
        return OptionalType(base=base, **self._pos(ctx))

    def visitUnionType(self, ctx: EzLangParser.UnionTypeContext):
        types = [t.accept(self) for t in ctx.type_()]
        return UnionType(types=types, **self._pos(ctx))

    def visitArrayType(self, ctx: EzLangParser.ArrayTypeContext):
        element = ctx.type_().accept(self)
        return ArrayType(element=element, **self._pos(ctx))

    def visitVecType(self, ctx: EzLangParser.VecTypeContext):
        element = ctx.type_().accept(self)
        size = int(ctx.INTEGER_LITERAL().getText())
        return VecType(element=element, size=size, **self._pos(ctx))

    def visitListType(self, ctx: EzLangParser.ListTypeContext):
        element = ctx.type_().accept(self)
        return ArrayType(element=element, **self._pos(ctx))

    def visitFunctionType(self, ctx: EzLangParser.FunctionTypeContext):
        params = self._visit_param_types(ctx.paramTypeList())
        return_type = ctx.type_().accept(self)
        return FunctionType(params=params, return_type=return_type, **self._pos(ctx))

    def visitBaseTypeRef(self, ctx: EzLangParser.BaseTypeRefContext):
        name = ctx.baseType().getText()
        if ctx.baseType().IDENTIFIER():
            return GenericType(
                base=BaseType(name=ctx.baseType().IDENTIFIER().getText()),
                args=self._visit_type_list(ctx.baseType().genericArgs()),
                **self._pos(ctx)
            )
        return BaseType(name=name, **self._pos(ctx))

    def visitTypeofType(self, ctx: EzLangParser.TypeofTypeContext):
        expr = ctx.expression().accept(self)
        return TypeofType(expr=expr, **self._pos(ctx))

    def visitParenType(self, ctx: EzLangParser.ParenTypeContext):
        return ctx.type_().accept(self)

    # === Expressions ===

    def visitLiteral(self, ctx: EzLangParser.LiteralContext):
        text = ctx.getText()
        if ctx.INTEGER_LITERAL():
            # Handle different bases
            if text.startswith('0b'):
                value = int(text[2:], 2)
            elif text.startswith('0o'):
                value = int(text[2:], 8)
            elif text.startswith('0x'):
                value = int(text[2:], 16)
            else:
                value = int(text.replace('_', ''))
            return LiteralExpr(value=value, type_name='integer', **self._pos(ctx))
        elif ctx.FLOAT_LITERAL():
            value = float(text.replace('_', ''))
            return LiteralExpr(value=value, type_name='float', **self._pos(ctx))
        elif ctx.STRING_LITERAL():
            value = text[1:-1]  # strip quotes
            return LiteralExpr(value=value, type_name='string', **self._pos(ctx))
        elif ctx.BOOL_LITERAL():
            value = text == 'true'
            return LiteralExpr(value=value, type_name='bool', **self._pos(ctx))
        return None

    def visitMemberAccess(self, ctx: EzLangParser.MemberAccessContext):
        obj = ctx.postfixExpression().accept(self)
        member = ctx.IDENTIFIER().getText()
        return MemberAccessExpr(object=obj, member=member, **self._pos(ctx))

    def visitCall(self, ctx: EzLangParser.CallContext):
        callee = ctx.postfixExpression().accept(self)
        args = self._visit_named_args(ctx.namedArgList())
        return CallExpr(callee=callee, args=args, **self._pos(ctx))

    def visitIndex(self, ctx: EzLangParser.IndexContext):
        array = ctx.postfixExpression().accept(self)
        index = ctx.expression().accept(self)
        return IndexExpr(array=array, index=index, **self._pos(ctx))

    def visitTypeAssertion(self, ctx: EzLangParser.TypeAssertionContext):
        expr = ctx.postfixExpression().accept(self)
        return TypeAssertionExpr(expr=expr, **self._pos(ctx))

    def visitOptionalUnwrap(self, ctx: EzLangParser.OptionalUnwrapContext):
        expr = ctx.postfixExpression().accept(self)
        return OptionalUnwrapExpr(expr=expr, **self._pos(ctx))

    def visitPipeline(self, ctx: EzLangParser.PipelineContext):
        value = ctx.postfixExpression().accept(self)
        func = ctx.IDENTIFIER().getText()
        args = self._visit_pipeline_args(ctx.pipelineArgList())
        return PipelineExpr(value=value, function=func, args=args, **self._pos(ctx))

    def visitStructLiteral(self, ctx: EzLangParser.StructLiteralContext):
        name = ctx.IDENTIFIER().getText()
        generic_args = self._visit_type_list(ctx.genericArgs())
        fields = {}
        spread = None
        if ctx.structFieldInitList():
            for init in ctx.structFieldInitList().structFieldInit():
                if init.ELLIPSIS():
                    spread = init.expression().accept(self)
                else:
                    fname = init.IDENTIFIER().getText()
                    fields[fname] = init.expression().accept(self)
        return StructLiteralExpr(
            struct_name=name,
            generic_args=generic_args,
            fields=fields,
            spread=spread,
            **self._pos(ctx)
        )

    def visitArrayLiteral(self, ctx: EzLangParser.ArrayLiteralContext):
        elements = self._visit_expression_list(ctx.expressionList())
        return ArrayLiteralExpr(elements=elements, **self._pos(ctx))

    def visitVecLiteral(self, ctx: EzLangParser.VecLiteralContext):
        elements = self._visit_expression_list(ctx.expressionList())
        return VecLiteralExpr(elements=elements, **self._pos(ctx))

    def visitFunctionLiteral(self, ctx: EzLangParser.FunctionLiteralContext):
        generic_params = self._visit_generic_params(ctx.genericParams())
        params = self._visit_params(ctx.paramList())
        return_type = ctx.type_().accept(self) if ctx.type_() else None
        body = ctx.expression().accept(self) if ctx.expression() else ctx.block().accept(self)
        return FunctionLiteralExpr(
            generic_params=generic_params,
            params=params,
            return_type=return_type,
            body=body,
            **self._pos(ctx)
        )

    def visitBlock(self, ctx: EzLangParser.BlockContext):
        stmts = [s.accept(self) for s in ctx.statement()]
        return BlockExpr(statements=stmts, **self._pos(ctx))

    def visitFlowBlock(self, ctx: EzLangParser.FlowBlockContext):
        body = ctx.block().accept(self)
        return FlowExpr(body=body, **self._pos(ctx))

    def visitMatchBlock(self, ctx: EzLangParser.MatchBlockContext):
        clauses = [c.accept(self) for c in ctx.matchClause()]
        return MatchExpr(clauses=clauses, **self._pos(ctx))

    def visitMatchClause(self, ctx: EzLangParser.MatchClauseContext):
        cond = ctx.expression().accept(self)
        body = ctx.expression().accept(self) if ctx.expression() else ctx.block().accept(self)
        return MatchClause(condition=cond, body=body, **self._pos(ctx))

    def visitCatchBlock(self, ctx: EzLangParser.CatchBlockContext):
        body = ctx.block().accept(self)
        return CatchExpr(body=body, **self._pos(ctx))

    def visitIfLikeExpr(self, ctx: EzLangParser.IfLikeExprContext):
        cond = ctx.expression(0).accept(self)
        then = ctx.expression(1).accept(self) if ctx.expression(1) else ctx.block(0).accept(self)
        else_ = None
        if ctx.COLON():
            if ctx.expression(2):
                else_ = ctx.expression(2).accept(self)
            elif ctx.block(1):
                else_ = ctx.block(1).accept(self)
        return IfLikeExpr(
            condition=cond,
            then_branch=then,
            else_branch=else_,
            **self._pos(ctx)
        )

    def visitLoopExpr(self, ctx: EzLangParser.LoopExprContext):
        var = ctx.IDENTIFIER().getText() if ctx.IDENTIFIER() else None
        range_expr = ctx.expression().accept(self) if ctx.expression() else None
        body = ctx.block().accept(self)
        return LoopExpr(
            variable=var,
            range_expr=range_expr,
            body=body,
            **self._pos(ctx)
        )

    def visitConditionalExpression(self, ctx: EzLangParser.ConditionalExpressionContext):
        if ctx.QUESTION() and ctx.COLON():
            cond = ctx.orExpression(0).accept(self)
            then = ctx.orExpression(1).accept(self)
            else_ = ctx.orExpression(2).accept(self)
            return ConditionalExpr(
                condition=cond,
                then_branch=then,
                else_branch=else_,
                **self._pos(ctx)
            )
        return self.visitChildren(ctx)

    # === Unary & Binary Operations ===

    def visitUnaryExpression(self, ctx: EzLangParser.UnaryExpressionContext):
        if ctx.getChildCount() == 2:
            op = ctx.getChild(0).getText()
            operand = ctx.unaryExpression().accept(self)
            return UnaryExpr(op=op, operand=operand, **self._pos(ctx))
        return self.visitChildren(ctx)

    def _visit_binary(self, ctx, op_index, expr_type):
        left = ctx.getChild(0).accept(self)
        op = ctx.getChild(op_index).getText()
        right = ctx.getChild(op_index + 1).accept(self)
        return BinaryExpr(op=op, left=left, right=right, **self._pos(ctx))

    def visitOrExpression(self, ctx: EzLangParser.OrExpressionContext):
        if ctx.OR():
            return self._visit_binary(ctx, 1, "or")
        return self.visitChildren(ctx)

    def visitAndExpression(self, ctx: EzLangParser.AndExpressionContext):
        if ctx.AND():
            return self._visit_binary(ctx, 1, "and")
        return self.visitChildren(ctx)

    def visitBitOrExpression(self, ctx: EzLangParser.BitOrExpressionContext):
        if ctx.PIPE():
            return self._visit_binary(ctx, 1, "bitor")
        return self.visitChildren(ctx)

    def visitBitXorExpression(self, ctx: EzLangParser.BitXorExpressionContext):
        if ctx.CARET():
            return self._visit_binary(ctx, 1, "bitxor")
        return self.visitChildren(ctx)

    def visitBitAndExpression(self, ctx: EzLangParser.BitAndExpressionContext):
        if ctx.AMPERSAND():
            return self._visit_binary(ctx, 1, "bitand")
        return self.visitChildren(ctx)

    def visitEqualityExpression(self, ctx: EzLangParser.EqualityExpressionContext):
        if ctx.EQ() or ctx.NE():
            return self._visit_binary(ctx, 1, "eq")
        return self.visitChildren(ctx)

    def visitRelationalExpression(self, ctx: EzLangParser.RelationalExpressionContext):
        if ctx.LANGLE() or ctx.RANGLE() or ctx.LE() or ctx.GE():
            return self._visit_binary(ctx, 1, "rel")
        return self.visitChildren(ctx)

    def visitShiftExpression(self, ctx: EzLangParser.ShiftExpressionContext):
        if ctx.SHL() or ctx.SHR():
            return self._visit_binary(ctx, 1, "shift")
        return self.visitChildren(ctx)

    def visitAdditiveExpression(self, ctx: EzLangParser.AdditiveExpressionContext):
        if ctx.PLUS() or ctx.MINUS():
            return self._visit_binary(ctx, 1, "add")
        return self.visitChildren(ctx)

    def visitMultiplicativeExpression(self, ctx: EzLangParser.MultiplicativeExpressionContext):
        if ctx.STAR() or ctx.SLASH() or ctx.PERCENT():
            return self._visit_binary(ctx, 1, "mul")
        return self.visitChildren(ctx)

    # === Statements ===

    def visitExpressionStatement(self, ctx: EzLangParser.ExpressionStatementContext):
        expr = ctx.expression().accept(self)
        return ExprStmt(expr=expr, **self._pos(ctx))

    def visitAssignmentStatement(self, ctx: EzLangParser.AssignmentStatementContext):
        lhs = ctx.expression(0).accept(self)
        op = ctx.assignmentOperator().getText()
        rhs = ctx.expression(1).accept(self)
        return AssignmentStmt(lhs=lhs, op=op, rhs=rhs, **self._pos(ctx))

    def visitReturnStatement(self, ctx: EzLangParser.ReturnStatementContext):
        value = ctx.expression().accept(self) if ctx.expression() else None
        return ReturnStmt(value=value, **self._pos(ctx))

    def visitBreakStatement(self, ctx: EzLangParser.BreakStatementContext):
        return BreakStmt(**self._pos(ctx))

    def visitContinueStatement(self, ctx: EzLangParser.ContinueStatementContext):
        return ContinueStmt(**self._pos(ctx))

    def visitThrowStatement(self, ctx: EzLangParser.ThrowStatementContext):
        value = ctx.expression().accept(self)
        return ThrowStmt(value=value, **self._pos(ctx))

    # === Helpers ===

    def _pos(self, ctx: ParserRuleContext):
        return {
            'line': ctx.start.line,
            'column': ctx.start.column
        }

    def _visit_generic_params(self, ctx):
        if not ctx:
            return []
        return [id.getText() for id in ctx.IDENTIFIER()]

    def _visit_type_list(self, ctx):
        if not ctx:
            return []
        return [t.accept(self) for t in ctx.type_()]

    def _visit_param_types(self, ctx):
        if not ctx:
            return []
        params = []
        for p in ctx.paramType():
            params.append(Param(
                name=p.IDENTIFIER().getText(),
                type_=p.type_().accept(self)
            ))
        return params

    def _visit_params(self, ctx):
        if not ctx:
            return []
        params = []
        for p in ctx.param():
            default = p.expression().accept(self) if p.expression() else None
            params.append(Param(
                name=p.IDENTIFIER().getText(),
                type_=p.type_().accept(self),
                default_value=default
            ))
        return params

    def _visit_named_args(self, ctx):
        if not ctx:
            return {}
        args = {}
        for arg in ctx.namedArg():
            name = arg.IDENTIFIER().getText()
            args[name] = arg.expression().accept(self)
        return args

    def _visit_pipeline_args(self, ctx):
        if not ctx:
            return {}
        args = {}
        for arg in ctx.pipelineArg():
            name = arg.IDENTIFIER().getText()
            if arg.expression():
                args[name] = arg.expression().accept(self)
            else:
                args[name] = '%'
        return args

    def _visit_expression_list(self, ctx):
        if not ctx:
            return []
        return [e.accept(self) for e in ctx.expression()]
