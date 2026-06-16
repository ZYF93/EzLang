# Generated from EzLang.g4 by ANTLR 4.13.2
from antlr4 import *
if "." in __name__:
    from .EzLangParser import EzLangParser
else:
    from EzLangParser import EzLangParser

# This class defines a complete generic visitor for a parse tree produced by EzLangParser.

class EzLangVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by EzLangParser#compilationUnit.
    def visitCompilationUnit(self, ctx:EzLangParser.CompilationUnitContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#declaration.
    def visitDeclaration(self, ctx:EzLangParser.DeclarationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#variableDecl.
    def visitVariableDecl(self, ctx:EzLangParser.VariableDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#lockPrefix.
    def visitLockPrefix(self, ctx:EzLangParser.LockPrefixContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#qualifiedVarName.
    def visitQualifiedVarName(self, ctx:EzLangParser.QualifiedVarNameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#decorator.
    def visitDecorator(self, ctx:EzLangParser.DecoratorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#structDecl.
    def visitStructDecl(self, ctx:EzLangParser.StructDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#structMember.
    def visitStructMember(self, ctx:EzLangParser.StructMemberContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#structSpread.
    def visitStructSpread(self, ctx:EzLangParser.StructSpreadContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#structField.
    def visitStructField(self, ctx:EzLangParser.StructFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#structMethod.
    def visitStructMethod(self, ctx:EzLangParser.StructMethodContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#typeAliasDecl.
    def visitTypeAliasDecl(self, ctx:EzLangParser.TypeAliasDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#typeShape.
    def visitTypeShape(self, ctx:EzLangParser.TypeShapeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#typeShapeMember.
    def visitTypeShapeMember(self, ctx:EzLangParser.TypeShapeMemberContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#typeShapeSpread.
    def visitTypeShapeSpread(self, ctx:EzLangParser.TypeShapeSpreadContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#functionDecl.
    def visitFunctionDecl(self, ctx:EzLangParser.FunctionDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#importDecl.
    def visitImportDecl(self, ctx:EzLangParser.ImportDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#importSpecList.
    def visitImportSpecList(self, ctx:EzLangParser.ImportSpecListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#importSpec.
    def visitImportSpec(self, ctx:EzLangParser.ImportSpecContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#importName.
    def visitImportName(self, ctx:EzLangParser.ImportNameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#exportDecl.
    def visitExportDecl(self, ctx:EzLangParser.ExportDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#externDecl.
    def visitExternDecl(self, ctx:EzLangParser.ExternDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#targetPlatform.
    def visitTargetPlatform(self, ctx:EzLangParser.TargetPlatformContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#declareDecl.
    def visitDeclareDecl(self, ctx:EzLangParser.DeclareDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#weakType.
    def visitWeakType(self, ctx:EzLangParser.WeakTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#arrayType.
    def visitArrayType(self, ctx:EzLangParser.ArrayTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#typeofType.
    def visitTypeofType(self, ctx:EzLangParser.TypeofTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#pointerType.
    def visitPointerType(self, ctx:EzLangParser.PointerTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#optionalType.
    def visitOptionalType(self, ctx:EzLangParser.OptionalTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#listType.
    def visitListType(self, ctx:EzLangParser.ListTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#functionTypeRef.
    def visitFunctionTypeRef(self, ctx:EzLangParser.FunctionTypeRefContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#genericFunctionType.
    def visitGenericFunctionType(self, ctx:EzLangParser.GenericFunctionTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#typeShapeType.
    def visitTypeShapeType(self, ctx:EzLangParser.TypeShapeTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#baseTypeRef.
    def visitBaseTypeRef(self, ctx:EzLangParser.BaseTypeRefContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#parenType.
    def visitParenType(self, ctx:EzLangParser.ParenTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#vecType.
    def visitVecType(self, ctx:EzLangParser.VecTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#genericParamFunctionType.
    def visitGenericParamFunctionType(self, ctx:EzLangParser.GenericParamFunctionTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#unionType.
    def visitUnionType(self, ctx:EzLangParser.UnionTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#baseType.
    def visitBaseType(self, ctx:EzLangParser.BaseTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#genericParams.
    def visitGenericParams(self, ctx:EzLangParser.GenericParamsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#genericArgs.
    def visitGenericArgs(self, ctx:EzLangParser.GenericArgsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#typeList.
    def visitTypeList(self, ctx:EzLangParser.TypeListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#functionType.
    def visitFunctionType(self, ctx:EzLangParser.FunctionTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#paramTypeList.
    def visitParamTypeList(self, ctx:EzLangParser.ParamTypeListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#paramType.
    def visitParamType(self, ctx:EzLangParser.ParamTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#expression.
    def visitExpression(self, ctx:EzLangParser.ExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#assignmentExpression.
    def visitAssignmentExpression(self, ctx:EzLangParser.AssignmentExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#assignmentOperator.
    def visitAssignmentOperator(self, ctx:EzLangParser.AssignmentOperatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#pipelineExpression.
    def visitPipelineExpression(self, ctx:EzLangParser.PipelineExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#conditionalExpression.
    def visitConditionalExpression(self, ctx:EzLangParser.ConditionalExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#rangeExpression.
    def visitRangeExpression(self, ctx:EzLangParser.RangeExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#orExpression.
    def visitOrExpression(self, ctx:EzLangParser.OrExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#andExpression.
    def visitAndExpression(self, ctx:EzLangParser.AndExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#equalityExpression.
    def visitEqualityExpression(self, ctx:EzLangParser.EqualityExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#relationalExpression.
    def visitRelationalExpression(self, ctx:EzLangParser.RelationalExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#bitOrExpression.
    def visitBitOrExpression(self, ctx:EzLangParser.BitOrExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#bitXorExpression.
    def visitBitXorExpression(self, ctx:EzLangParser.BitXorExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#bitAndExpression.
    def visitBitAndExpression(self, ctx:EzLangParser.BitAndExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#shiftExpression.
    def visitShiftExpression(self, ctx:EzLangParser.ShiftExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#shiftOperator.
    def visitShiftOperator(self, ctx:EzLangParser.ShiftOperatorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#additiveExpression.
    def visitAdditiveExpression(self, ctx:EzLangParser.AdditiveExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#multiplicativeExpression.
    def visitMultiplicativeExpression(self, ctx:EzLangParser.MultiplicativeExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#prefixTypeAssertion.
    def visitPrefixTypeAssertion(self, ctx:EzLangParser.PrefixTypeAssertionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#weakRefExpression.
    def visitWeakRefExpression(self, ctx:EzLangParser.WeakRefExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#prefixUnaryExpression.
    def visitPrefixUnaryExpression(self, ctx:EzLangParser.PrefixUnaryExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#postfixUnaryExpression.
    def visitPostfixUnaryExpression(self, ctx:EzLangParser.PostfixUnaryExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#call.
    def visitCall(self, ctx:EzLangParser.CallContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#typeAssertion.
    def visitTypeAssertion(self, ctx:EzLangParser.TypeAssertionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#pipeline.
    def visitPipeline(self, ctx:EzLangParser.PipelineContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#memberAccess.
    def visitMemberAccess(self, ctx:EzLangParser.MemberAccessContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#primaryExpr.
    def visitPrimaryExpr(self, ctx:EzLangParser.PrimaryExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#index.
    def visitIndex(self, ctx:EzLangParser.IndexContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#optionalUnwrap.
    def visitOptionalUnwrap(self, ctx:EzLangParser.OptionalUnwrapContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#literalExpr.
    def visitLiteralExpr(self, ctx:EzLangParser.LiteralExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#structLiteralExpr.
    def visitStructLiteralExpr(self, ctx:EzLangParser.StructLiteralExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#identifierExpr.
    def visitIdentifierExpr(self, ctx:EzLangParser.IdentifierExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#ifLikePrimaryExpr.
    def visitIfLikePrimaryExpr(self, ctx:EzLangParser.IfLikePrimaryExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#parenExpr.
    def visitParenExpr(self, ctx:EzLangParser.ParenExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#placeholderExpr.
    def visitPlaceholderExpr(self, ctx:EzLangParser.PlaceholderExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#dictExpr.
    def visitDictExpr(self, ctx:EzLangParser.DictExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#blockExpr.
    def visitBlockExpr(self, ctx:EzLangParser.BlockExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#arrayLiteralExpr.
    def visitArrayLiteralExpr(self, ctx:EzLangParser.ArrayLiteralExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#vecLiteralExpr.
    def visitVecLiteralExpr(self, ctx:EzLangParser.VecLiteralExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#fnLiteralExpr.
    def visitFnLiteralExpr(self, ctx:EzLangParser.FnLiteralExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#flowBlockExpr.
    def visitFlowBlockExpr(self, ctx:EzLangParser.FlowBlockExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#parallelBlockExpr.
    def visitParallelBlockExpr(self, ctx:EzLangParser.ParallelBlockExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#matchBlockExpr.
    def visitMatchBlockExpr(self, ctx:EzLangParser.MatchBlockExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#catchBlockExpr.
    def visitCatchBlockExpr(self, ctx:EzLangParser.CatchBlockExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#loopPrimaryExpr.
    def visitLoopPrimaryExpr(self, ctx:EzLangParser.LoopPrimaryExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#typeofPrimaryExpr.
    def visitTypeofPrimaryExpr(self, ctx:EzLangParser.TypeofPrimaryExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#markupExpr.
    def visitMarkupExpr(self, ctx:EzLangParser.MarkupExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#typeofExpr.
    def visitTypeofExpr(self, ctx:EzLangParser.TypeofExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#literal.
    def visitLiteral(self, ctx:EzLangParser.LiteralContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#namedArgList.
    def visitNamedArgList(self, ctx:EzLangParser.NamedArgListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#callArg.
    def visitCallArg(self, ctx:EzLangParser.CallArgContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#namedArg.
    def visitNamedArg(self, ctx:EzLangParser.NamedArgContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#pipelineArgList.
    def visitPipelineArgList(self, ctx:EzLangParser.PipelineArgListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#pipelineArg.
    def visitPipelineArg(self, ctx:EzLangParser.PipelineArgContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#structLiteral.
    def visitStructLiteral(self, ctx:EzLangParser.StructLiteralContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#structFieldInitList.
    def visitStructFieldInitList(self, ctx:EzLangParser.StructFieldInitListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#structFieldInit.
    def visitStructFieldInit(self, ctx:EzLangParser.StructFieldInitContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#dictLiteral.
    def visitDictLiteral(self, ctx:EzLangParser.DictLiteralContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#dictFieldSep.
    def visitDictFieldSep(self, ctx:EzLangParser.DictFieldSepContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#dictField.
    def visitDictField(self, ctx:EzLangParser.DictFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#dictKey.
    def visitDictKey(self, ctx:EzLangParser.DictKeyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#arrayLiteral.
    def visitArrayLiteral(self, ctx:EzLangParser.ArrayLiteralContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#vecLiteral.
    def visitVecLiteral(self, ctx:EzLangParser.VecLiteralContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#expressionList.
    def visitExpressionList(self, ctx:EzLangParser.ExpressionListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#markupLiteral.
    def visitMarkupLiteral(self, ctx:EzLangParser.MarkupLiteralContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#markupAttr.
    def visitMarkupAttr(self, ctx:EzLangParser.MarkupAttrContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#markupChild.
    def visitMarkupChild(self, ctx:EzLangParser.MarkupChildContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#functionLiteral.
    def visitFunctionLiteral(self, ctx:EzLangParser.FunctionLiteralContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#functionSignature.
    def visitFunctionSignature(self, ctx:EzLangParser.FunctionSignatureContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#paramList.
    def visitParamList(self, ctx:EzLangParser.ParamListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#param.
    def visitParam(self, ctx:EzLangParser.ParamContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#block.
    def visitBlock(self, ctx:EzLangParser.BlockContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#flowBlock.
    def visitFlowBlock(self, ctx:EzLangParser.FlowBlockContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#parallelBlock.
    def visitParallelBlock(self, ctx:EzLangParser.ParallelBlockContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#matchBlock.
    def visitMatchBlock(self, ctx:EzLangParser.MatchBlockContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#matchClause.
    def visitMatchClause(self, ctx:EzLangParser.MatchClauseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#catchBlock.
    def visitCatchBlock(self, ctx:EzLangParser.CatchBlockContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#ifLikeExpr.
    def visitIfLikeExpr(self, ctx:EzLangParser.IfLikeExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#loopExpr.
    def visitLoopExpr(self, ctx:EzLangParser.LoopExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#statement.
    def visitStatement(self, ctx:EzLangParser.StatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#expressionStatement.
    def visitExpressionStatement(self, ctx:EzLangParser.ExpressionStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#returnStatement.
    def visitReturnStatement(self, ctx:EzLangParser.ReturnStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#breakStatement.
    def visitBreakStatement(self, ctx:EzLangParser.BreakStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#continueStatement.
    def visitContinueStatement(self, ctx:EzLangParser.ContinueStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#throwStatement.
    def visitThrowStatement(self, ctx:EzLangParser.ThrowStatementContext):
        return self.visitChildren(ctx)



del EzLangParser