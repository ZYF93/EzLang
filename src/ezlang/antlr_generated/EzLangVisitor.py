# Generated from grammar/EzLang.g4 by ANTLR 4.13.2
from antlr4 import *
if "." in __name__:
    from .EzLangParser import EzLangParser
else:
    from EzLangParser import EzLangParser

# This class defines a complete generic visitor for a parse tree produced by EzLangParser.

class EzLangVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by EzLangParser#program.
    def visitProgram(self, ctx:EzLangParser.ProgramContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#statement.
    def visitStatement(self, ctx:EzLangParser.StatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#typeDeclaration.
    def visitTypeDeclaration(self, ctx:EzLangParser.TypeDeclarationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#anonymousStruct.
    def visitAnonymousStruct(self, ctx:EzLangParser.AnonymousStructContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#variableDeclaration.
    def visitVariableDeclaration(self, ctx:EzLangParser.VariableDeclarationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#structDeclaration.
    def visitStructDeclaration(self, ctx:EzLangParser.StructDeclarationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#structBody.
    def visitStructBody(self, ctx:EzLangParser.StructBodyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#baseStruct.
    def visitBaseStruct(self, ctx:EzLangParser.BaseStructContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#field.
    def visitField(self, ctx:EzLangParser.FieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#method.
    def visitMethod(self, ctx:EzLangParser.MethodContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#functionDeclaration.
    def visitFunctionDeclaration(self, ctx:EzLangParser.FunctionDeclarationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#functionExpression.
    def visitFunctionExpression(self, ctx:EzLangParser.FunctionExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#parameters.
    def visitParameters(self, ctx:EzLangParser.ParametersContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#parameter.
    def visitParameter(self, ctx:EzLangParser.ParameterContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#block.
    def visitBlock(self, ctx:EzLangParser.BlockContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#blockStatement.
    def visitBlockStatement(self, ctx:EzLangParser.BlockStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#breakStatement.
    def visitBreakStatement(self, ctx:EzLangParser.BreakStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#continueStatement.
    def visitContinueStatement(self, ctx:EzLangParser.ContinueStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#returnStatement.
    def visitReturnStatement(self, ctx:EzLangParser.ReturnStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#importStatement.
    def visitImportStatement(self, ctx:EzLangParser.ImportStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#importItems.
    def visitImportItems(self, ctx:EzLangParser.ImportItemsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#importItem.
    def visitImportItem(self, ctx:EzLangParser.ImportItemContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#exportStatement.
    def visitExportStatement(self, ctx:EzLangParser.ExportStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#declareStatement.
    def visitDeclareStatement(self, ctx:EzLangParser.DeclareStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#expression.
    def visitExpression(self, ctx:EzLangParser.ExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#assignmentExpression.
    def visitAssignmentExpression(self, ctx:EzLangParser.AssignmentExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#assignmentOp.
    def visitAssignmentOp(self, ctx:EzLangParser.AssignmentOpContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#pipelineExpression.
    def visitPipelineExpression(self, ctx:EzLangParser.PipelineExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#conditionalExpression.
    def visitConditionalExpression(self, ctx:EzLangParser.ConditionalExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#controlFlowOnly.
    def visitControlFlowOnly(self, ctx:EzLangParser.ControlFlowOnlyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#logicalOrExpression.
    def visitLogicalOrExpression(self, ctx:EzLangParser.LogicalOrExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#logicalAndExpression.
    def visitLogicalAndExpression(self, ctx:EzLangParser.LogicalAndExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#equalityExpression.
    def visitEqualityExpression(self, ctx:EzLangParser.EqualityExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#equalityOp.
    def visitEqualityOp(self, ctx:EzLangParser.EqualityOpContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#relationalExpression.
    def visitRelationalExpression(self, ctx:EzLangParser.RelationalExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#relationalOp.
    def visitRelationalOp(self, ctx:EzLangParser.RelationalOpContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#shiftExpression.
    def visitShiftExpression(self, ctx:EzLangParser.ShiftExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#shiftOp.
    def visitShiftOp(self, ctx:EzLangParser.ShiftOpContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#additiveExpression.
    def visitAdditiveExpression(self, ctx:EzLangParser.AdditiveExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#addOp.
    def visitAddOp(self, ctx:EzLangParser.AddOpContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#multiplicativeExpression.
    def visitMultiplicativeExpression(self, ctx:EzLangParser.MultiplicativeExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#mulOp.
    def visitMulOp(self, ctx:EzLangParser.MulOpContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#unaryExpression.
    def visitUnaryExpression(self, ctx:EzLangParser.UnaryExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#postfixExpression.
    def visitPostfixExpression(self, ctx:EzLangParser.PostfixExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#postfix.
    def visitPostfix(self, ctx:EzLangParser.PostfixContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#argumentList.
    def visitArgumentList(self, ctx:EzLangParser.ArgumentListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#namedArgument.
    def visitNamedArgument(self, ctx:EzLangParser.NamedArgumentContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#primaryExpression.
    def visitPrimaryExpression(self, ctx:EzLangParser.PrimaryExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#catchExpression.
    def visitCatchExpression(self, ctx:EzLangParser.CatchExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#throwExpression.
    def visitThrowExpression(self, ctx:EzLangParser.ThrowExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#awaitExpression.
    def visitAwaitExpression(self, ctx:EzLangParser.AwaitExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#literal.
    def visitLiteral(self, ctx:EzLangParser.LiteralContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#vectorLiteral.
    def visitVectorLiteral(self, ctx:EzLangParser.VectorLiteralContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#structLiteral.
    def visitStructLiteral(self, ctx:EzLangParser.StructLiteralContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#structFields.
    def visitStructFields(self, ctx:EzLangParser.StructFieldsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#structField.
    def visitStructField(self, ctx:EzLangParser.StructFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#markupLiteral.
    def visitMarkupLiteral(self, ctx:EzLangParser.MarkupLiteralContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#markupAttrs.
    def visitMarkupAttrs(self, ctx:EzLangParser.MarkupAttrsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#markupAttr.
    def visitMarkupAttr(self, ctx:EzLangParser.MarkupAttrContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#markupContent.
    def visitMarkupContent(self, ctx:EzLangParser.MarkupContentContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#expressionStatement.
    def visitExpressionStatement(self, ctx:EzLangParser.ExpressionStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#type.
    def visitType(self, ctx:EzLangParser.TypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#simpleType.
    def visitSimpleType(self, ctx:EzLangParser.SimpleTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#typeSuffix.
    def visitTypeSuffix(self, ctx:EzLangParser.TypeSuffixContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#baseType.
    def visitBaseType(self, ctx:EzLangParser.BaseTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#functionType.
    def visitFunctionType(self, ctx:EzLangParser.FunctionTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#genericArgs.
    def visitGenericArgs(self, ctx:EzLangParser.GenericArgsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#genericParams.
    def visitGenericParams(self, ctx:EzLangParser.GenericParamsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#decorator.
    def visitDecorator(self, ctx:EzLangParser.DecoratorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#controlStatement.
    def visitControlStatement(self, ctx:EzLangParser.ControlStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#loopStatement.
    def visitLoopStatement(self, ctx:EzLangParser.LoopStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#infiniteLoop.
    def visitInfiniteLoop(self, ctx:EzLangParser.InfiniteLoopContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#rangeLoop.
    def visitRangeLoop(self, ctx:EzLangParser.RangeLoopContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#conditionalStatement.
    def visitConditionalStatement(self, ctx:EzLangParser.ConditionalStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#matchStatement.
    def visitMatchStatement(self, ctx:EzLangParser.MatchStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#matchCase.
    def visitMatchCase(self, ctx:EzLangParser.MatchCaseContext):
        return self.visitChildren(ctx)



del EzLangParser