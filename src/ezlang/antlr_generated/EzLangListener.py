# Generated from grammar/EzLang.g4 by ANTLR 4.13.2
from antlr4 import *
if "." in __name__:
    from .EzLangParser import EzLangParser
else:
    from EzLangParser import EzLangParser

# This class defines a complete listener for a parse tree produced by EzLangParser.
class EzLangListener(ParseTreeListener):

    # Enter a parse tree produced by EzLangParser#program.
    def enterProgram(self, ctx:EzLangParser.ProgramContext):
        pass

    # Exit a parse tree produced by EzLangParser#program.
    def exitProgram(self, ctx:EzLangParser.ProgramContext):
        pass


    # Enter a parse tree produced by EzLangParser#statement.
    def enterStatement(self, ctx:EzLangParser.StatementContext):
        pass

    # Exit a parse tree produced by EzLangParser#statement.
    def exitStatement(self, ctx:EzLangParser.StatementContext):
        pass


    # Enter a parse tree produced by EzLangParser#typeDeclaration.
    def enterTypeDeclaration(self, ctx:EzLangParser.TypeDeclarationContext):
        pass

    # Exit a parse tree produced by EzLangParser#typeDeclaration.
    def exitTypeDeclaration(self, ctx:EzLangParser.TypeDeclarationContext):
        pass


    # Enter a parse tree produced by EzLangParser#anonymousStruct.
    def enterAnonymousStruct(self, ctx:EzLangParser.AnonymousStructContext):
        pass

    # Exit a parse tree produced by EzLangParser#anonymousStruct.
    def exitAnonymousStruct(self, ctx:EzLangParser.AnonymousStructContext):
        pass


    # Enter a parse tree produced by EzLangParser#variableDeclaration.
    def enterVariableDeclaration(self, ctx:EzLangParser.VariableDeclarationContext):
        pass

    # Exit a parse tree produced by EzLangParser#variableDeclaration.
    def exitVariableDeclaration(self, ctx:EzLangParser.VariableDeclarationContext):
        pass


    # Enter a parse tree produced by EzLangParser#structDeclaration.
    def enterStructDeclaration(self, ctx:EzLangParser.StructDeclarationContext):
        pass

    # Exit a parse tree produced by EzLangParser#structDeclaration.
    def exitStructDeclaration(self, ctx:EzLangParser.StructDeclarationContext):
        pass


    # Enter a parse tree produced by EzLangParser#structBody.
    def enterStructBody(self, ctx:EzLangParser.StructBodyContext):
        pass

    # Exit a parse tree produced by EzLangParser#structBody.
    def exitStructBody(self, ctx:EzLangParser.StructBodyContext):
        pass


    # Enter a parse tree produced by EzLangParser#baseStruct.
    def enterBaseStruct(self, ctx:EzLangParser.BaseStructContext):
        pass

    # Exit a parse tree produced by EzLangParser#baseStruct.
    def exitBaseStruct(self, ctx:EzLangParser.BaseStructContext):
        pass


    # Enter a parse tree produced by EzLangParser#field.
    def enterField(self, ctx:EzLangParser.FieldContext):
        pass

    # Exit a parse tree produced by EzLangParser#field.
    def exitField(self, ctx:EzLangParser.FieldContext):
        pass


    # Enter a parse tree produced by EzLangParser#method.
    def enterMethod(self, ctx:EzLangParser.MethodContext):
        pass

    # Exit a parse tree produced by EzLangParser#method.
    def exitMethod(self, ctx:EzLangParser.MethodContext):
        pass


    # Enter a parse tree produced by EzLangParser#functionDeclaration.
    def enterFunctionDeclaration(self, ctx:EzLangParser.FunctionDeclarationContext):
        pass

    # Exit a parse tree produced by EzLangParser#functionDeclaration.
    def exitFunctionDeclaration(self, ctx:EzLangParser.FunctionDeclarationContext):
        pass


    # Enter a parse tree produced by EzLangParser#functionExpression.
    def enterFunctionExpression(self, ctx:EzLangParser.FunctionExpressionContext):
        pass

    # Exit a parse tree produced by EzLangParser#functionExpression.
    def exitFunctionExpression(self, ctx:EzLangParser.FunctionExpressionContext):
        pass


    # Enter a parse tree produced by EzLangParser#parameters.
    def enterParameters(self, ctx:EzLangParser.ParametersContext):
        pass

    # Exit a parse tree produced by EzLangParser#parameters.
    def exitParameters(self, ctx:EzLangParser.ParametersContext):
        pass


    # Enter a parse tree produced by EzLangParser#parameter.
    def enterParameter(self, ctx:EzLangParser.ParameterContext):
        pass

    # Exit a parse tree produced by EzLangParser#parameter.
    def exitParameter(self, ctx:EzLangParser.ParameterContext):
        pass


    # Enter a parse tree produced by EzLangParser#block.
    def enterBlock(self, ctx:EzLangParser.BlockContext):
        pass

    # Exit a parse tree produced by EzLangParser#block.
    def exitBlock(self, ctx:EzLangParser.BlockContext):
        pass


    # Enter a parse tree produced by EzLangParser#blockStatement.
    def enterBlockStatement(self, ctx:EzLangParser.BlockStatementContext):
        pass

    # Exit a parse tree produced by EzLangParser#blockStatement.
    def exitBlockStatement(self, ctx:EzLangParser.BlockStatementContext):
        pass


    # Enter a parse tree produced by EzLangParser#breakStatement.
    def enterBreakStatement(self, ctx:EzLangParser.BreakStatementContext):
        pass

    # Exit a parse tree produced by EzLangParser#breakStatement.
    def exitBreakStatement(self, ctx:EzLangParser.BreakStatementContext):
        pass


    # Enter a parse tree produced by EzLangParser#continueStatement.
    def enterContinueStatement(self, ctx:EzLangParser.ContinueStatementContext):
        pass

    # Exit a parse tree produced by EzLangParser#continueStatement.
    def exitContinueStatement(self, ctx:EzLangParser.ContinueStatementContext):
        pass


    # Enter a parse tree produced by EzLangParser#returnStatement.
    def enterReturnStatement(self, ctx:EzLangParser.ReturnStatementContext):
        pass

    # Exit a parse tree produced by EzLangParser#returnStatement.
    def exitReturnStatement(self, ctx:EzLangParser.ReturnStatementContext):
        pass


    # Enter a parse tree produced by EzLangParser#importStatement.
    def enterImportStatement(self, ctx:EzLangParser.ImportStatementContext):
        pass

    # Exit a parse tree produced by EzLangParser#importStatement.
    def exitImportStatement(self, ctx:EzLangParser.ImportStatementContext):
        pass


    # Enter a parse tree produced by EzLangParser#importItems.
    def enterImportItems(self, ctx:EzLangParser.ImportItemsContext):
        pass

    # Exit a parse tree produced by EzLangParser#importItems.
    def exitImportItems(self, ctx:EzLangParser.ImportItemsContext):
        pass


    # Enter a parse tree produced by EzLangParser#importItem.
    def enterImportItem(self, ctx:EzLangParser.ImportItemContext):
        pass

    # Exit a parse tree produced by EzLangParser#importItem.
    def exitImportItem(self, ctx:EzLangParser.ImportItemContext):
        pass


    # Enter a parse tree produced by EzLangParser#exportStatement.
    def enterExportStatement(self, ctx:EzLangParser.ExportStatementContext):
        pass

    # Exit a parse tree produced by EzLangParser#exportStatement.
    def exitExportStatement(self, ctx:EzLangParser.ExportStatementContext):
        pass


    # Enter a parse tree produced by EzLangParser#declareStatement.
    def enterDeclareStatement(self, ctx:EzLangParser.DeclareStatementContext):
        pass

    # Exit a parse tree produced by EzLangParser#declareStatement.
    def exitDeclareStatement(self, ctx:EzLangParser.DeclareStatementContext):
        pass


    # Enter a parse tree produced by EzLangParser#expression.
    def enterExpression(self, ctx:EzLangParser.ExpressionContext):
        pass

    # Exit a parse tree produced by EzLangParser#expression.
    def exitExpression(self, ctx:EzLangParser.ExpressionContext):
        pass


    # Enter a parse tree produced by EzLangParser#assignmentExpression.
    def enterAssignmentExpression(self, ctx:EzLangParser.AssignmentExpressionContext):
        pass

    # Exit a parse tree produced by EzLangParser#assignmentExpression.
    def exitAssignmentExpression(self, ctx:EzLangParser.AssignmentExpressionContext):
        pass


    # Enter a parse tree produced by EzLangParser#assignmentOp.
    def enterAssignmentOp(self, ctx:EzLangParser.AssignmentOpContext):
        pass

    # Exit a parse tree produced by EzLangParser#assignmentOp.
    def exitAssignmentOp(self, ctx:EzLangParser.AssignmentOpContext):
        pass


    # Enter a parse tree produced by EzLangParser#pipelineExpression.
    def enterPipelineExpression(self, ctx:EzLangParser.PipelineExpressionContext):
        pass

    # Exit a parse tree produced by EzLangParser#pipelineExpression.
    def exitPipelineExpression(self, ctx:EzLangParser.PipelineExpressionContext):
        pass


    # Enter a parse tree produced by EzLangParser#conditionalExpression.
    def enterConditionalExpression(self, ctx:EzLangParser.ConditionalExpressionContext):
        pass

    # Exit a parse tree produced by EzLangParser#conditionalExpression.
    def exitConditionalExpression(self, ctx:EzLangParser.ConditionalExpressionContext):
        pass


    # Enter a parse tree produced by EzLangParser#controlFlowOnly.
    def enterControlFlowOnly(self, ctx:EzLangParser.ControlFlowOnlyContext):
        pass

    # Exit a parse tree produced by EzLangParser#controlFlowOnly.
    def exitControlFlowOnly(self, ctx:EzLangParser.ControlFlowOnlyContext):
        pass


    # Enter a parse tree produced by EzLangParser#logicalOrExpression.
    def enterLogicalOrExpression(self, ctx:EzLangParser.LogicalOrExpressionContext):
        pass

    # Exit a parse tree produced by EzLangParser#logicalOrExpression.
    def exitLogicalOrExpression(self, ctx:EzLangParser.LogicalOrExpressionContext):
        pass


    # Enter a parse tree produced by EzLangParser#logicalAndExpression.
    def enterLogicalAndExpression(self, ctx:EzLangParser.LogicalAndExpressionContext):
        pass

    # Exit a parse tree produced by EzLangParser#logicalAndExpression.
    def exitLogicalAndExpression(self, ctx:EzLangParser.LogicalAndExpressionContext):
        pass


    # Enter a parse tree produced by EzLangParser#equalityExpression.
    def enterEqualityExpression(self, ctx:EzLangParser.EqualityExpressionContext):
        pass

    # Exit a parse tree produced by EzLangParser#equalityExpression.
    def exitEqualityExpression(self, ctx:EzLangParser.EqualityExpressionContext):
        pass


    # Enter a parse tree produced by EzLangParser#equalityOp.
    def enterEqualityOp(self, ctx:EzLangParser.EqualityOpContext):
        pass

    # Exit a parse tree produced by EzLangParser#equalityOp.
    def exitEqualityOp(self, ctx:EzLangParser.EqualityOpContext):
        pass


    # Enter a parse tree produced by EzLangParser#relationalExpression.
    def enterRelationalExpression(self, ctx:EzLangParser.RelationalExpressionContext):
        pass

    # Exit a parse tree produced by EzLangParser#relationalExpression.
    def exitRelationalExpression(self, ctx:EzLangParser.RelationalExpressionContext):
        pass


    # Enter a parse tree produced by EzLangParser#relationalOp.
    def enterRelationalOp(self, ctx:EzLangParser.RelationalOpContext):
        pass

    # Exit a parse tree produced by EzLangParser#relationalOp.
    def exitRelationalOp(self, ctx:EzLangParser.RelationalOpContext):
        pass


    # Enter a parse tree produced by EzLangParser#bitwiseOrExpression.
    def enterBitwiseOrExpression(self, ctx:EzLangParser.BitwiseOrExpressionContext):
        pass

    # Exit a parse tree produced by EzLangParser#bitwiseOrExpression.
    def exitBitwiseOrExpression(self, ctx:EzLangParser.BitwiseOrExpressionContext):
        pass


    # Enter a parse tree produced by EzLangParser#bitwiseXorExpression.
    def enterBitwiseXorExpression(self, ctx:EzLangParser.BitwiseXorExpressionContext):
        pass

    # Exit a parse tree produced by EzLangParser#bitwiseXorExpression.
    def exitBitwiseXorExpression(self, ctx:EzLangParser.BitwiseXorExpressionContext):
        pass


    # Enter a parse tree produced by EzLangParser#bitwiseAndExpression.
    def enterBitwiseAndExpression(self, ctx:EzLangParser.BitwiseAndExpressionContext):
        pass

    # Exit a parse tree produced by EzLangParser#bitwiseAndExpression.
    def exitBitwiseAndExpression(self, ctx:EzLangParser.BitwiseAndExpressionContext):
        pass


    # Enter a parse tree produced by EzLangParser#shiftExpression.
    def enterShiftExpression(self, ctx:EzLangParser.ShiftExpressionContext):
        pass

    # Exit a parse tree produced by EzLangParser#shiftExpression.
    def exitShiftExpression(self, ctx:EzLangParser.ShiftExpressionContext):
        pass


    # Enter a parse tree produced by EzLangParser#shiftOp.
    def enterShiftOp(self, ctx:EzLangParser.ShiftOpContext):
        pass

    # Exit a parse tree produced by EzLangParser#shiftOp.
    def exitShiftOp(self, ctx:EzLangParser.ShiftOpContext):
        pass


    # Enter a parse tree produced by EzLangParser#additiveExpression.
    def enterAdditiveExpression(self, ctx:EzLangParser.AdditiveExpressionContext):
        pass

    # Exit a parse tree produced by EzLangParser#additiveExpression.
    def exitAdditiveExpression(self, ctx:EzLangParser.AdditiveExpressionContext):
        pass


    # Enter a parse tree produced by EzLangParser#addOp.
    def enterAddOp(self, ctx:EzLangParser.AddOpContext):
        pass

    # Exit a parse tree produced by EzLangParser#addOp.
    def exitAddOp(self, ctx:EzLangParser.AddOpContext):
        pass


    # Enter a parse tree produced by EzLangParser#multiplicativeExpression.
    def enterMultiplicativeExpression(self, ctx:EzLangParser.MultiplicativeExpressionContext):
        pass

    # Exit a parse tree produced by EzLangParser#multiplicativeExpression.
    def exitMultiplicativeExpression(self, ctx:EzLangParser.MultiplicativeExpressionContext):
        pass


    # Enter a parse tree produced by EzLangParser#mulOp.
    def enterMulOp(self, ctx:EzLangParser.MulOpContext):
        pass

    # Exit a parse tree produced by EzLangParser#mulOp.
    def exitMulOp(self, ctx:EzLangParser.MulOpContext):
        pass


    # Enter a parse tree produced by EzLangParser#unaryExpression.
    def enterUnaryExpression(self, ctx:EzLangParser.UnaryExpressionContext):
        pass

    # Exit a parse tree produced by EzLangParser#unaryExpression.
    def exitUnaryExpression(self, ctx:EzLangParser.UnaryExpressionContext):
        pass


    # Enter a parse tree produced by EzLangParser#postfixExpression.
    def enterPostfixExpression(self, ctx:EzLangParser.PostfixExpressionContext):
        pass

    # Exit a parse tree produced by EzLangParser#postfixExpression.
    def exitPostfixExpression(self, ctx:EzLangParser.PostfixExpressionContext):
        pass


    # Enter a parse tree produced by EzLangParser#postfix.
    def enterPostfix(self, ctx:EzLangParser.PostfixContext):
        pass

    # Exit a parse tree produced by EzLangParser#postfix.
    def exitPostfix(self, ctx:EzLangParser.PostfixContext):
        pass


    # Enter a parse tree produced by EzLangParser#argumentList.
    def enterArgumentList(self, ctx:EzLangParser.ArgumentListContext):
        pass

    # Exit a parse tree produced by EzLangParser#argumentList.
    def exitArgumentList(self, ctx:EzLangParser.ArgumentListContext):
        pass


    # Enter a parse tree produced by EzLangParser#namedArgument.
    def enterNamedArgument(self, ctx:EzLangParser.NamedArgumentContext):
        pass

    # Exit a parse tree produced by EzLangParser#namedArgument.
    def exitNamedArgument(self, ctx:EzLangParser.NamedArgumentContext):
        pass


    # Enter a parse tree produced by EzLangParser#primaryExpression.
    def enterPrimaryExpression(self, ctx:EzLangParser.PrimaryExpressionContext):
        pass

    # Exit a parse tree produced by EzLangParser#primaryExpression.
    def exitPrimaryExpression(self, ctx:EzLangParser.PrimaryExpressionContext):
        pass


    # Enter a parse tree produced by EzLangParser#catchExpression.
    def enterCatchExpression(self, ctx:EzLangParser.CatchExpressionContext):
        pass

    # Exit a parse tree produced by EzLangParser#catchExpression.
    def exitCatchExpression(self, ctx:EzLangParser.CatchExpressionContext):
        pass


    # Enter a parse tree produced by EzLangParser#throwExpression.
    def enterThrowExpression(self, ctx:EzLangParser.ThrowExpressionContext):
        pass

    # Exit a parse tree produced by EzLangParser#throwExpression.
    def exitThrowExpression(self, ctx:EzLangParser.ThrowExpressionContext):
        pass


    # Enter a parse tree produced by EzLangParser#awaitExpression.
    def enterAwaitExpression(self, ctx:EzLangParser.AwaitExpressionContext):
        pass

    # Exit a parse tree produced by EzLangParser#awaitExpression.
    def exitAwaitExpression(self, ctx:EzLangParser.AwaitExpressionContext):
        pass


    # Enter a parse tree produced by EzLangParser#literal.
    def enterLiteral(self, ctx:EzLangParser.LiteralContext):
        pass

    # Exit a parse tree produced by EzLangParser#literal.
    def exitLiteral(self, ctx:EzLangParser.LiteralContext):
        pass


    # Enter a parse tree produced by EzLangParser#vectorLiteral.
    def enterVectorLiteral(self, ctx:EzLangParser.VectorLiteralContext):
        pass

    # Exit a parse tree produced by EzLangParser#vectorLiteral.
    def exitVectorLiteral(self, ctx:EzLangParser.VectorLiteralContext):
        pass


    # Enter a parse tree produced by EzLangParser#structLiteral.
    def enterStructLiteral(self, ctx:EzLangParser.StructLiteralContext):
        pass

    # Exit a parse tree produced by EzLangParser#structLiteral.
    def exitStructLiteral(self, ctx:EzLangParser.StructLiteralContext):
        pass


    # Enter a parse tree produced by EzLangParser#structFields.
    def enterStructFields(self, ctx:EzLangParser.StructFieldsContext):
        pass

    # Exit a parse tree produced by EzLangParser#structFields.
    def exitStructFields(self, ctx:EzLangParser.StructFieldsContext):
        pass


    # Enter a parse tree produced by EzLangParser#structField.
    def enterStructField(self, ctx:EzLangParser.StructFieldContext):
        pass

    # Exit a parse tree produced by EzLangParser#structField.
    def exitStructField(self, ctx:EzLangParser.StructFieldContext):
        pass


    # Enter a parse tree produced by EzLangParser#markupLiteral.
    def enterMarkupLiteral(self, ctx:EzLangParser.MarkupLiteralContext):
        pass

    # Exit a parse tree produced by EzLangParser#markupLiteral.
    def exitMarkupLiteral(self, ctx:EzLangParser.MarkupLiteralContext):
        pass


    # Enter a parse tree produced by EzLangParser#markupAttrs.
    def enterMarkupAttrs(self, ctx:EzLangParser.MarkupAttrsContext):
        pass

    # Exit a parse tree produced by EzLangParser#markupAttrs.
    def exitMarkupAttrs(self, ctx:EzLangParser.MarkupAttrsContext):
        pass


    # Enter a parse tree produced by EzLangParser#markupAttr.
    def enterMarkupAttr(self, ctx:EzLangParser.MarkupAttrContext):
        pass

    # Exit a parse tree produced by EzLangParser#markupAttr.
    def exitMarkupAttr(self, ctx:EzLangParser.MarkupAttrContext):
        pass


    # Enter a parse tree produced by EzLangParser#markupContent.
    def enterMarkupContent(self, ctx:EzLangParser.MarkupContentContext):
        pass

    # Exit a parse tree produced by EzLangParser#markupContent.
    def exitMarkupContent(self, ctx:EzLangParser.MarkupContentContext):
        pass


    # Enter a parse tree produced by EzLangParser#expressionStatement.
    def enterExpressionStatement(self, ctx:EzLangParser.ExpressionStatementContext):
        pass

    # Exit a parse tree produced by EzLangParser#expressionStatement.
    def exitExpressionStatement(self, ctx:EzLangParser.ExpressionStatementContext):
        pass


    # Enter a parse tree produced by EzLangParser#type.
    def enterType(self, ctx:EzLangParser.TypeContext):
        pass

    # Exit a parse tree produced by EzLangParser#type.
    def exitType(self, ctx:EzLangParser.TypeContext):
        pass


    # Enter a parse tree produced by EzLangParser#simpleType.
    def enterSimpleType(self, ctx:EzLangParser.SimpleTypeContext):
        pass

    # Exit a parse tree produced by EzLangParser#simpleType.
    def exitSimpleType(self, ctx:EzLangParser.SimpleTypeContext):
        pass


    # Enter a parse tree produced by EzLangParser#typeSuffix.
    def enterTypeSuffix(self, ctx:EzLangParser.TypeSuffixContext):
        pass

    # Exit a parse tree produced by EzLangParser#typeSuffix.
    def exitTypeSuffix(self, ctx:EzLangParser.TypeSuffixContext):
        pass


    # Enter a parse tree produced by EzLangParser#baseType.
    def enterBaseType(self, ctx:EzLangParser.BaseTypeContext):
        pass

    # Exit a parse tree produced by EzLangParser#baseType.
    def exitBaseType(self, ctx:EzLangParser.BaseTypeContext):
        pass


    # Enter a parse tree produced by EzLangParser#functionType.
    def enterFunctionType(self, ctx:EzLangParser.FunctionTypeContext):
        pass

    # Exit a parse tree produced by EzLangParser#functionType.
    def exitFunctionType(self, ctx:EzLangParser.FunctionTypeContext):
        pass


    # Enter a parse tree produced by EzLangParser#genericArgs.
    def enterGenericArgs(self, ctx:EzLangParser.GenericArgsContext):
        pass

    # Exit a parse tree produced by EzLangParser#genericArgs.
    def exitGenericArgs(self, ctx:EzLangParser.GenericArgsContext):
        pass


    # Enter a parse tree produced by EzLangParser#genericParams.
    def enterGenericParams(self, ctx:EzLangParser.GenericParamsContext):
        pass

    # Exit a parse tree produced by EzLangParser#genericParams.
    def exitGenericParams(self, ctx:EzLangParser.GenericParamsContext):
        pass


    # Enter a parse tree produced by EzLangParser#decorator.
    def enterDecorator(self, ctx:EzLangParser.DecoratorContext):
        pass

    # Exit a parse tree produced by EzLangParser#decorator.
    def exitDecorator(self, ctx:EzLangParser.DecoratorContext):
        pass


    # Enter a parse tree produced by EzLangParser#controlStatement.
    def enterControlStatement(self, ctx:EzLangParser.ControlStatementContext):
        pass

    # Exit a parse tree produced by EzLangParser#controlStatement.
    def exitControlStatement(self, ctx:EzLangParser.ControlStatementContext):
        pass


    # Enter a parse tree produced by EzLangParser#loopStatement.
    def enterLoopStatement(self, ctx:EzLangParser.LoopStatementContext):
        pass

    # Exit a parse tree produced by EzLangParser#loopStatement.
    def exitLoopStatement(self, ctx:EzLangParser.LoopStatementContext):
        pass


    # Enter a parse tree produced by EzLangParser#infiniteLoop.
    def enterInfiniteLoop(self, ctx:EzLangParser.InfiniteLoopContext):
        pass

    # Exit a parse tree produced by EzLangParser#infiniteLoop.
    def exitInfiniteLoop(self, ctx:EzLangParser.InfiniteLoopContext):
        pass


    # Enter a parse tree produced by EzLangParser#rangeLoop.
    def enterRangeLoop(self, ctx:EzLangParser.RangeLoopContext):
        pass

    # Exit a parse tree produced by EzLangParser#rangeLoop.
    def exitRangeLoop(self, ctx:EzLangParser.RangeLoopContext):
        pass


    # Enter a parse tree produced by EzLangParser#conditionalStatement.
    def enterConditionalStatement(self, ctx:EzLangParser.ConditionalStatementContext):
        pass

    # Exit a parse tree produced by EzLangParser#conditionalStatement.
    def exitConditionalStatement(self, ctx:EzLangParser.ConditionalStatementContext):
        pass


    # Enter a parse tree produced by EzLangParser#matchStatement.
    def enterMatchStatement(self, ctx:EzLangParser.MatchStatementContext):
        pass

    # Exit a parse tree produced by EzLangParser#matchStatement.
    def exitMatchStatement(self, ctx:EzLangParser.MatchStatementContext):
        pass


    # Enter a parse tree produced by EzLangParser#matchCase.
    def enterMatchCase(self, ctx:EzLangParser.MatchCaseContext):
        pass

    # Exit a parse tree produced by EzLangParser#matchCase.
    def exitMatchCase(self, ctx:EzLangParser.MatchCaseContext):
        pass



del EzLangParser