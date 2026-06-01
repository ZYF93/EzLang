# Generated from grammar/EzLang.g4 by ANTLR 4.13.2
from antlr4 import *
if "." in __name__:
    from .EzLangParser import EzLangParser
else:
    from EzLangParser import EzLangParser

# This class defines a complete listener for a parse tree produced by EzLangParser.
class EzLangListener(ParseTreeListener):

    # Enter a parse tree produced by EzLangParser#compilationUnit.
    def enterCompilationUnit(self, ctx:EzLangParser.CompilationUnitContext):
        pass

    # Exit a parse tree produced by EzLangParser#compilationUnit.
    def exitCompilationUnit(self, ctx:EzLangParser.CompilationUnitContext):
        pass


    # Enter a parse tree produced by EzLangParser#declaration.
    def enterDeclaration(self, ctx:EzLangParser.DeclarationContext):
        pass

    # Exit a parse tree produced by EzLangParser#declaration.
    def exitDeclaration(self, ctx:EzLangParser.DeclarationContext):
        pass


    # Enter a parse tree produced by EzLangParser#variableDecl.
    def enterVariableDecl(self, ctx:EzLangParser.VariableDeclContext):
        pass

    # Exit a parse tree produced by EzLangParser#variableDecl.
    def exitVariableDecl(self, ctx:EzLangParser.VariableDeclContext):
        pass


    # Enter a parse tree produced by EzLangParser#structDecl.
    def enterStructDecl(self, ctx:EzLangParser.StructDeclContext):
        pass

    # Exit a parse tree produced by EzLangParser#structDecl.
    def exitStructDecl(self, ctx:EzLangParser.StructDeclContext):
        pass


    # Enter a parse tree produced by EzLangParser#structMember.
    def enterStructMember(self, ctx:EzLangParser.StructMemberContext):
        pass

    # Exit a parse tree produced by EzLangParser#structMember.
    def exitStructMember(self, ctx:EzLangParser.StructMemberContext):
        pass


    # Enter a parse tree produced by EzLangParser#structSpread.
    def enterStructSpread(self, ctx:EzLangParser.StructSpreadContext):
        pass

    # Exit a parse tree produced by EzLangParser#structSpread.
    def exitStructSpread(self, ctx:EzLangParser.StructSpreadContext):
        pass


    # Enter a parse tree produced by EzLangParser#structField.
    def enterStructField(self, ctx:EzLangParser.StructFieldContext):
        pass

    # Exit a parse tree produced by EzLangParser#structField.
    def exitStructField(self, ctx:EzLangParser.StructFieldContext):
        pass


    # Enter a parse tree produced by EzLangParser#structMethod.
    def enterStructMethod(self, ctx:EzLangParser.StructMethodContext):
        pass

    # Exit a parse tree produced by EzLangParser#structMethod.
    def exitStructMethod(self, ctx:EzLangParser.StructMethodContext):
        pass


    # Enter a parse tree produced by EzLangParser#typeAliasDecl.
    def enterTypeAliasDecl(self, ctx:EzLangParser.TypeAliasDeclContext):
        pass

    # Exit a parse tree produced by EzLangParser#typeAliasDecl.
    def exitTypeAliasDecl(self, ctx:EzLangParser.TypeAliasDeclContext):
        pass


    # Enter a parse tree produced by EzLangParser#typeShape.
    def enterTypeShape(self, ctx:EzLangParser.TypeShapeContext):
        pass

    # Exit a parse tree produced by EzLangParser#typeShape.
    def exitTypeShape(self, ctx:EzLangParser.TypeShapeContext):
        pass


    # Enter a parse tree produced by EzLangParser#typeShapeMember.
    def enterTypeShapeMember(self, ctx:EzLangParser.TypeShapeMemberContext):
        pass

    # Exit a parse tree produced by EzLangParser#typeShapeMember.
    def exitTypeShapeMember(self, ctx:EzLangParser.TypeShapeMemberContext):
        pass


    # Enter a parse tree produced by EzLangParser#typeShapeSpread.
    def enterTypeShapeSpread(self, ctx:EzLangParser.TypeShapeSpreadContext):
        pass

    # Exit a parse tree produced by EzLangParser#typeShapeSpread.
    def exitTypeShapeSpread(self, ctx:EzLangParser.TypeShapeSpreadContext):
        pass


    # Enter a parse tree produced by EzLangParser#functionDecl.
    def enterFunctionDecl(self, ctx:EzLangParser.FunctionDeclContext):
        pass

    # Exit a parse tree produced by EzLangParser#functionDecl.
    def exitFunctionDecl(self, ctx:EzLangParser.FunctionDeclContext):
        pass


    # Enter a parse tree produced by EzLangParser#importDecl.
    def enterImportDecl(self, ctx:EzLangParser.ImportDeclContext):
        pass

    # Exit a parse tree produced by EzLangParser#importDecl.
    def exitImportDecl(self, ctx:EzLangParser.ImportDeclContext):
        pass


    # Enter a parse tree produced by EzLangParser#importSpecList.
    def enterImportSpecList(self, ctx:EzLangParser.ImportSpecListContext):
        pass

    # Exit a parse tree produced by EzLangParser#importSpecList.
    def exitImportSpecList(self, ctx:EzLangParser.ImportSpecListContext):
        pass


    # Enter a parse tree produced by EzLangParser#importSpec.
    def enterImportSpec(self, ctx:EzLangParser.ImportSpecContext):
        pass

    # Exit a parse tree produced by EzLangParser#importSpec.
    def exitImportSpec(self, ctx:EzLangParser.ImportSpecContext):
        pass


    # Enter a parse tree produced by EzLangParser#exportDecl.
    def enterExportDecl(self, ctx:EzLangParser.ExportDeclContext):
        pass

    # Exit a parse tree produced by EzLangParser#exportDecl.
    def exitExportDecl(self, ctx:EzLangParser.ExportDeclContext):
        pass


    # Enter a parse tree produced by EzLangParser#externDecl.
    def enterExternDecl(self, ctx:EzLangParser.ExternDeclContext):
        pass

    # Exit a parse tree produced by EzLangParser#externDecl.
    def exitExternDecl(self, ctx:EzLangParser.ExternDeclContext):
        pass


    # Enter a parse tree produced by EzLangParser#targetPlatform.
    def enterTargetPlatform(self, ctx:EzLangParser.TargetPlatformContext):
        pass

    # Exit a parse tree produced by EzLangParser#targetPlatform.
    def exitTargetPlatform(self, ctx:EzLangParser.TargetPlatformContext):
        pass


    # Enter a parse tree produced by EzLangParser#declareDecl.
    def enterDeclareDecl(self, ctx:EzLangParser.DeclareDeclContext):
        pass

    # Exit a parse tree produced by EzLangParser#declareDecl.
    def exitDeclareDecl(self, ctx:EzLangParser.DeclareDeclContext):
        pass


    # Enter a parse tree produced by EzLangParser#arrayType.
    def enterArrayType(self, ctx:EzLangParser.ArrayTypeContext):
        pass

    # Exit a parse tree produced by EzLangParser#arrayType.
    def exitArrayType(self, ctx:EzLangParser.ArrayTypeContext):
        pass


    # Enter a parse tree produced by EzLangParser#typeofType.
    def enterTypeofType(self, ctx:EzLangParser.TypeofTypeContext):
        pass

    # Exit a parse tree produced by EzLangParser#typeofType.
    def exitTypeofType(self, ctx:EzLangParser.TypeofTypeContext):
        pass


    # Enter a parse tree produced by EzLangParser#functionTypeRef.
    def enterFunctionTypeRef(self, ctx:EzLangParser.FunctionTypeRefContext):
        pass

    # Exit a parse tree produced by EzLangParser#functionTypeRef.
    def exitFunctionTypeRef(self, ctx:EzLangParser.FunctionTypeRefContext):
        pass


    # Enter a parse tree produced by EzLangParser#optionalType.
    def enterOptionalType(self, ctx:EzLangParser.OptionalTypeContext):
        pass

    # Exit a parse tree produced by EzLangParser#optionalType.
    def exitOptionalType(self, ctx:EzLangParser.OptionalTypeContext):
        pass


    # Enter a parse tree produced by EzLangParser#genericFunctionType.
    def enterGenericFunctionType(self, ctx:EzLangParser.GenericFunctionTypeContext):
        pass

    # Exit a parse tree produced by EzLangParser#genericFunctionType.
    def exitGenericFunctionType(self, ctx:EzLangParser.GenericFunctionTypeContext):
        pass


    # Enter a parse tree produced by EzLangParser#baseTypeRef.
    def enterBaseTypeRef(self, ctx:EzLangParser.BaseTypeRefContext):
        pass

    # Exit a parse tree produced by EzLangParser#baseTypeRef.
    def exitBaseTypeRef(self, ctx:EzLangParser.BaseTypeRefContext):
        pass


    # Enter a parse tree produced by EzLangParser#parenType.
    def enterParenType(self, ctx:EzLangParser.ParenTypeContext):
        pass

    # Exit a parse tree produced by EzLangParser#parenType.
    def exitParenType(self, ctx:EzLangParser.ParenTypeContext):
        pass


    # Enter a parse tree produced by EzLangParser#vecType.
    def enterVecType(self, ctx:EzLangParser.VecTypeContext):
        pass

    # Exit a parse tree produced by EzLangParser#vecType.
    def exitVecType(self, ctx:EzLangParser.VecTypeContext):
        pass


    # Enter a parse tree produced by EzLangParser#listType.
    def enterListType(self, ctx:EzLangParser.ListTypeContext):
        pass

    # Exit a parse tree produced by EzLangParser#listType.
    def exitListType(self, ctx:EzLangParser.ListTypeContext):
        pass


    # Enter a parse tree produced by EzLangParser#unionType.
    def enterUnionType(self, ctx:EzLangParser.UnionTypeContext):
        pass

    # Exit a parse tree produced by EzLangParser#unionType.
    def exitUnionType(self, ctx:EzLangParser.UnionTypeContext):
        pass


    # Enter a parse tree produced by EzLangParser#baseType.
    def enterBaseType(self, ctx:EzLangParser.BaseTypeContext):
        pass

    # Exit a parse tree produced by EzLangParser#baseType.
    def exitBaseType(self, ctx:EzLangParser.BaseTypeContext):
        pass


    # Enter a parse tree produced by EzLangParser#genericParams.
    def enterGenericParams(self, ctx:EzLangParser.GenericParamsContext):
        pass

    # Exit a parse tree produced by EzLangParser#genericParams.
    def exitGenericParams(self, ctx:EzLangParser.GenericParamsContext):
        pass


    # Enter a parse tree produced by EzLangParser#genericArgs.
    def enterGenericArgs(self, ctx:EzLangParser.GenericArgsContext):
        pass

    # Exit a parse tree produced by EzLangParser#genericArgs.
    def exitGenericArgs(self, ctx:EzLangParser.GenericArgsContext):
        pass


    # Enter a parse tree produced by EzLangParser#typeList.
    def enterTypeList(self, ctx:EzLangParser.TypeListContext):
        pass

    # Exit a parse tree produced by EzLangParser#typeList.
    def exitTypeList(self, ctx:EzLangParser.TypeListContext):
        pass


    # Enter a parse tree produced by EzLangParser#functionType.
    def enterFunctionType(self, ctx:EzLangParser.FunctionTypeContext):
        pass

    # Exit a parse tree produced by EzLangParser#functionType.
    def exitFunctionType(self, ctx:EzLangParser.FunctionTypeContext):
        pass


    # Enter a parse tree produced by EzLangParser#paramTypeList.
    def enterParamTypeList(self, ctx:EzLangParser.ParamTypeListContext):
        pass

    # Exit a parse tree produced by EzLangParser#paramTypeList.
    def exitParamTypeList(self, ctx:EzLangParser.ParamTypeListContext):
        pass


    # Enter a parse tree produced by EzLangParser#paramType.
    def enterParamType(self, ctx:EzLangParser.ParamTypeContext):
        pass

    # Exit a parse tree produced by EzLangParser#paramType.
    def exitParamType(self, ctx:EzLangParser.ParamTypeContext):
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


    # Enter a parse tree produced by EzLangParser#assignmentOperator.
    def enterAssignmentOperator(self, ctx:EzLangParser.AssignmentOperatorContext):
        pass

    # Exit a parse tree produced by EzLangParser#assignmentOperator.
    def exitAssignmentOperator(self, ctx:EzLangParser.AssignmentOperatorContext):
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


    # Enter a parse tree produced by EzLangParser#rangeExpression.
    def enterRangeExpression(self, ctx:EzLangParser.RangeExpressionContext):
        pass

    # Exit a parse tree produced by EzLangParser#rangeExpression.
    def exitRangeExpression(self, ctx:EzLangParser.RangeExpressionContext):
        pass


    # Enter a parse tree produced by EzLangParser#orExpression.
    def enterOrExpression(self, ctx:EzLangParser.OrExpressionContext):
        pass

    # Exit a parse tree produced by EzLangParser#orExpression.
    def exitOrExpression(self, ctx:EzLangParser.OrExpressionContext):
        pass


    # Enter a parse tree produced by EzLangParser#andExpression.
    def enterAndExpression(self, ctx:EzLangParser.AndExpressionContext):
        pass

    # Exit a parse tree produced by EzLangParser#andExpression.
    def exitAndExpression(self, ctx:EzLangParser.AndExpressionContext):
        pass


    # Enter a parse tree produced by EzLangParser#bitOrExpression.
    def enterBitOrExpression(self, ctx:EzLangParser.BitOrExpressionContext):
        pass

    # Exit a parse tree produced by EzLangParser#bitOrExpression.
    def exitBitOrExpression(self, ctx:EzLangParser.BitOrExpressionContext):
        pass


    # Enter a parse tree produced by EzLangParser#bitXorExpression.
    def enterBitXorExpression(self, ctx:EzLangParser.BitXorExpressionContext):
        pass

    # Exit a parse tree produced by EzLangParser#bitXorExpression.
    def exitBitXorExpression(self, ctx:EzLangParser.BitXorExpressionContext):
        pass


    # Enter a parse tree produced by EzLangParser#bitAndExpression.
    def enterBitAndExpression(self, ctx:EzLangParser.BitAndExpressionContext):
        pass

    # Exit a parse tree produced by EzLangParser#bitAndExpression.
    def exitBitAndExpression(self, ctx:EzLangParser.BitAndExpressionContext):
        pass


    # Enter a parse tree produced by EzLangParser#equalityExpression.
    def enterEqualityExpression(self, ctx:EzLangParser.EqualityExpressionContext):
        pass

    # Exit a parse tree produced by EzLangParser#equalityExpression.
    def exitEqualityExpression(self, ctx:EzLangParser.EqualityExpressionContext):
        pass


    # Enter a parse tree produced by EzLangParser#relationalExpression.
    def enterRelationalExpression(self, ctx:EzLangParser.RelationalExpressionContext):
        pass

    # Exit a parse tree produced by EzLangParser#relationalExpression.
    def exitRelationalExpression(self, ctx:EzLangParser.RelationalExpressionContext):
        pass


    # Enter a parse tree produced by EzLangParser#shiftExpression.
    def enterShiftExpression(self, ctx:EzLangParser.ShiftExpressionContext):
        pass

    # Exit a parse tree produced by EzLangParser#shiftExpression.
    def exitShiftExpression(self, ctx:EzLangParser.ShiftExpressionContext):
        pass


    # Enter a parse tree produced by EzLangParser#additiveExpression.
    def enterAdditiveExpression(self, ctx:EzLangParser.AdditiveExpressionContext):
        pass

    # Exit a parse tree produced by EzLangParser#additiveExpression.
    def exitAdditiveExpression(self, ctx:EzLangParser.AdditiveExpressionContext):
        pass


    # Enter a parse tree produced by EzLangParser#multiplicativeExpression.
    def enterMultiplicativeExpression(self, ctx:EzLangParser.MultiplicativeExpressionContext):
        pass

    # Exit a parse tree produced by EzLangParser#multiplicativeExpression.
    def exitMultiplicativeExpression(self, ctx:EzLangParser.MultiplicativeExpressionContext):
        pass


    # Enter a parse tree produced by EzLangParser#unaryExpression.
    def enterUnaryExpression(self, ctx:EzLangParser.UnaryExpressionContext):
        pass

    # Exit a parse tree produced by EzLangParser#unaryExpression.
    def exitUnaryExpression(self, ctx:EzLangParser.UnaryExpressionContext):
        pass


    # Enter a parse tree produced by EzLangParser#call.
    def enterCall(self, ctx:EzLangParser.CallContext):
        pass

    # Exit a parse tree produced by EzLangParser#call.
    def exitCall(self, ctx:EzLangParser.CallContext):
        pass


    # Enter a parse tree produced by EzLangParser#typeAssertion.
    def enterTypeAssertion(self, ctx:EzLangParser.TypeAssertionContext):
        pass

    # Exit a parse tree produced by EzLangParser#typeAssertion.
    def exitTypeAssertion(self, ctx:EzLangParser.TypeAssertionContext):
        pass


    # Enter a parse tree produced by EzLangParser#pipeline.
    def enterPipeline(self, ctx:EzLangParser.PipelineContext):
        pass

    # Exit a parse tree produced by EzLangParser#pipeline.
    def exitPipeline(self, ctx:EzLangParser.PipelineContext):
        pass


    # Enter a parse tree produced by EzLangParser#memberAccess.
    def enterMemberAccess(self, ctx:EzLangParser.MemberAccessContext):
        pass

    # Exit a parse tree produced by EzLangParser#memberAccess.
    def exitMemberAccess(self, ctx:EzLangParser.MemberAccessContext):
        pass


    # Enter a parse tree produced by EzLangParser#primaryExpr.
    def enterPrimaryExpr(self, ctx:EzLangParser.PrimaryExprContext):
        pass

    # Exit a parse tree produced by EzLangParser#primaryExpr.
    def exitPrimaryExpr(self, ctx:EzLangParser.PrimaryExprContext):
        pass


    # Enter a parse tree produced by EzLangParser#index.
    def enterIndex(self, ctx:EzLangParser.IndexContext):
        pass

    # Exit a parse tree produced by EzLangParser#index.
    def exitIndex(self, ctx:EzLangParser.IndexContext):
        pass


    # Enter a parse tree produced by EzLangParser#optionalUnwrap.
    def enterOptionalUnwrap(self, ctx:EzLangParser.OptionalUnwrapContext):
        pass

    # Exit a parse tree produced by EzLangParser#optionalUnwrap.
    def exitOptionalUnwrap(self, ctx:EzLangParser.OptionalUnwrapContext):
        pass


    # Enter a parse tree produced by EzLangParser#literalExpr.
    def enterLiteralExpr(self, ctx:EzLangParser.LiteralExprContext):
        pass

    # Exit a parse tree produced by EzLangParser#literalExpr.
    def exitLiteralExpr(self, ctx:EzLangParser.LiteralExprContext):
        pass


    # Enter a parse tree produced by EzLangParser#identifierExpr.
    def enterIdentifierExpr(self, ctx:EzLangParser.IdentifierExprContext):
        pass

    # Exit a parse tree produced by EzLangParser#identifierExpr.
    def exitIdentifierExpr(self, ctx:EzLangParser.IdentifierExprContext):
        pass


    # Enter a parse tree produced by EzLangParser#parenExpr.
    def enterParenExpr(self, ctx:EzLangParser.ParenExprContext):
        pass

    # Exit a parse tree produced by EzLangParser#parenExpr.
    def exitParenExpr(self, ctx:EzLangParser.ParenExprContext):
        pass


    # Enter a parse tree produced by EzLangParser#placeholderExpr.
    def enterPlaceholderExpr(self, ctx:EzLangParser.PlaceholderExprContext):
        pass

    # Exit a parse tree produced by EzLangParser#placeholderExpr.
    def exitPlaceholderExpr(self, ctx:EzLangParser.PlaceholderExprContext):
        pass


    # Enter a parse tree produced by EzLangParser#dictExpr.
    def enterDictExpr(self, ctx:EzLangParser.DictExprContext):
        pass

    # Exit a parse tree produced by EzLangParser#dictExpr.
    def exitDictExpr(self, ctx:EzLangParser.DictExprContext):
        pass


    # Enter a parse tree produced by EzLangParser#blockExpr.
    def enterBlockExpr(self, ctx:EzLangParser.BlockExprContext):
        pass

    # Exit a parse tree produced by EzLangParser#blockExpr.
    def exitBlockExpr(self, ctx:EzLangParser.BlockExprContext):
        pass


    # Enter a parse tree produced by EzLangParser#structLiteralExpr.
    def enterStructLiteralExpr(self, ctx:EzLangParser.StructLiteralExprContext):
        pass

    # Exit a parse tree produced by EzLangParser#structLiteralExpr.
    def exitStructLiteralExpr(self, ctx:EzLangParser.StructLiteralExprContext):
        pass


    # Enter a parse tree produced by EzLangParser#arrayLiteralExpr.
    def enterArrayLiteralExpr(self, ctx:EzLangParser.ArrayLiteralExprContext):
        pass

    # Exit a parse tree produced by EzLangParser#arrayLiteralExpr.
    def exitArrayLiteralExpr(self, ctx:EzLangParser.ArrayLiteralExprContext):
        pass


    # Enter a parse tree produced by EzLangParser#vecLiteralExpr.
    def enterVecLiteralExpr(self, ctx:EzLangParser.VecLiteralExprContext):
        pass

    # Exit a parse tree produced by EzLangParser#vecLiteralExpr.
    def exitVecLiteralExpr(self, ctx:EzLangParser.VecLiteralExprContext):
        pass


    # Enter a parse tree produced by EzLangParser#fnLiteralExpr.
    def enterFnLiteralExpr(self, ctx:EzLangParser.FnLiteralExprContext):
        pass

    # Exit a parse tree produced by EzLangParser#fnLiteralExpr.
    def exitFnLiteralExpr(self, ctx:EzLangParser.FnLiteralExprContext):
        pass


    # Enter a parse tree produced by EzLangParser#flowBlockExpr.
    def enterFlowBlockExpr(self, ctx:EzLangParser.FlowBlockExprContext):
        pass

    # Exit a parse tree produced by EzLangParser#flowBlockExpr.
    def exitFlowBlockExpr(self, ctx:EzLangParser.FlowBlockExprContext):
        pass


    # Enter a parse tree produced by EzLangParser#matchBlockExpr.
    def enterMatchBlockExpr(self, ctx:EzLangParser.MatchBlockExprContext):
        pass

    # Exit a parse tree produced by EzLangParser#matchBlockExpr.
    def exitMatchBlockExpr(self, ctx:EzLangParser.MatchBlockExprContext):
        pass


    # Enter a parse tree produced by EzLangParser#catchBlockExpr.
    def enterCatchBlockExpr(self, ctx:EzLangParser.CatchBlockExprContext):
        pass

    # Exit a parse tree produced by EzLangParser#catchBlockExpr.
    def exitCatchBlockExpr(self, ctx:EzLangParser.CatchBlockExprContext):
        pass


    # Enter a parse tree produced by EzLangParser#loopPrimaryExpr.
    def enterLoopPrimaryExpr(self, ctx:EzLangParser.LoopPrimaryExprContext):
        pass

    # Exit a parse tree produced by EzLangParser#loopPrimaryExpr.
    def exitLoopPrimaryExpr(self, ctx:EzLangParser.LoopPrimaryExprContext):
        pass


    # Enter a parse tree produced by EzLangParser#ifLikePrimaryExpr.
    def enterIfLikePrimaryExpr(self, ctx:EzLangParser.IfLikePrimaryExprContext):
        pass

    # Exit a parse tree produced by EzLangParser#ifLikePrimaryExpr.
    def exitIfLikePrimaryExpr(self, ctx:EzLangParser.IfLikePrimaryExprContext):
        pass


    # Enter a parse tree produced by EzLangParser#typeofPrimaryExpr.
    def enterTypeofPrimaryExpr(self, ctx:EzLangParser.TypeofPrimaryExprContext):
        pass

    # Exit a parse tree produced by EzLangParser#typeofPrimaryExpr.
    def exitTypeofPrimaryExpr(self, ctx:EzLangParser.TypeofPrimaryExprContext):
        pass


    # Enter a parse tree produced by EzLangParser#typeofExpr.
    def enterTypeofExpr(self, ctx:EzLangParser.TypeofExprContext):
        pass

    # Exit a parse tree produced by EzLangParser#typeofExpr.
    def exitTypeofExpr(self, ctx:EzLangParser.TypeofExprContext):
        pass


    # Enter a parse tree produced by EzLangParser#literal.
    def enterLiteral(self, ctx:EzLangParser.LiteralContext):
        pass

    # Exit a parse tree produced by EzLangParser#literal.
    def exitLiteral(self, ctx:EzLangParser.LiteralContext):
        pass


    # Enter a parse tree produced by EzLangParser#namedArgList.
    def enterNamedArgList(self, ctx:EzLangParser.NamedArgListContext):
        pass

    # Exit a parse tree produced by EzLangParser#namedArgList.
    def exitNamedArgList(self, ctx:EzLangParser.NamedArgListContext):
        pass


    # Enter a parse tree produced by EzLangParser#namedArg.
    def enterNamedArg(self, ctx:EzLangParser.NamedArgContext):
        pass

    # Exit a parse tree produced by EzLangParser#namedArg.
    def exitNamedArg(self, ctx:EzLangParser.NamedArgContext):
        pass


    # Enter a parse tree produced by EzLangParser#pipelineArgList.
    def enterPipelineArgList(self, ctx:EzLangParser.PipelineArgListContext):
        pass

    # Exit a parse tree produced by EzLangParser#pipelineArgList.
    def exitPipelineArgList(self, ctx:EzLangParser.PipelineArgListContext):
        pass


    # Enter a parse tree produced by EzLangParser#pipelineArg.
    def enterPipelineArg(self, ctx:EzLangParser.PipelineArgContext):
        pass

    # Exit a parse tree produced by EzLangParser#pipelineArg.
    def exitPipelineArg(self, ctx:EzLangParser.PipelineArgContext):
        pass


    # Enter a parse tree produced by EzLangParser#structLiteral.
    def enterStructLiteral(self, ctx:EzLangParser.StructLiteralContext):
        pass

    # Exit a parse tree produced by EzLangParser#structLiteral.
    def exitStructLiteral(self, ctx:EzLangParser.StructLiteralContext):
        pass


    # Enter a parse tree produced by EzLangParser#structFieldInitList.
    def enterStructFieldInitList(self, ctx:EzLangParser.StructFieldInitListContext):
        pass

    # Exit a parse tree produced by EzLangParser#structFieldInitList.
    def exitStructFieldInitList(self, ctx:EzLangParser.StructFieldInitListContext):
        pass


    # Enter a parse tree produced by EzLangParser#structFieldInit.
    def enterStructFieldInit(self, ctx:EzLangParser.StructFieldInitContext):
        pass

    # Exit a parse tree produced by EzLangParser#structFieldInit.
    def exitStructFieldInit(self, ctx:EzLangParser.StructFieldInitContext):
        pass


    # Enter a parse tree produced by EzLangParser#dictLiteral.
    def enterDictLiteral(self, ctx:EzLangParser.DictLiteralContext):
        pass

    # Exit a parse tree produced by EzLangParser#dictLiteral.
    def exitDictLiteral(self, ctx:EzLangParser.DictLiteralContext):
        pass


    # Enter a parse tree produced by EzLangParser#dictField.
    def enterDictField(self, ctx:EzLangParser.DictFieldContext):
        pass

    # Exit a parse tree produced by EzLangParser#dictField.
    def exitDictField(self, ctx:EzLangParser.DictFieldContext):
        pass


    # Enter a parse tree produced by EzLangParser#arrayLiteral.
    def enterArrayLiteral(self, ctx:EzLangParser.ArrayLiteralContext):
        pass

    # Exit a parse tree produced by EzLangParser#arrayLiteral.
    def exitArrayLiteral(self, ctx:EzLangParser.ArrayLiteralContext):
        pass


    # Enter a parse tree produced by EzLangParser#vecLiteral.
    def enterVecLiteral(self, ctx:EzLangParser.VecLiteralContext):
        pass

    # Exit a parse tree produced by EzLangParser#vecLiteral.
    def exitVecLiteral(self, ctx:EzLangParser.VecLiteralContext):
        pass


    # Enter a parse tree produced by EzLangParser#expressionList.
    def enterExpressionList(self, ctx:EzLangParser.ExpressionListContext):
        pass

    # Exit a parse tree produced by EzLangParser#expressionList.
    def exitExpressionList(self, ctx:EzLangParser.ExpressionListContext):
        pass


    # Enter a parse tree produced by EzLangParser#functionLiteral.
    def enterFunctionLiteral(self, ctx:EzLangParser.FunctionLiteralContext):
        pass

    # Exit a parse tree produced by EzLangParser#functionLiteral.
    def exitFunctionLiteral(self, ctx:EzLangParser.FunctionLiteralContext):
        pass


    # Enter a parse tree produced by EzLangParser#paramList.
    def enterParamList(self, ctx:EzLangParser.ParamListContext):
        pass

    # Exit a parse tree produced by EzLangParser#paramList.
    def exitParamList(self, ctx:EzLangParser.ParamListContext):
        pass


    # Enter a parse tree produced by EzLangParser#param.
    def enterParam(self, ctx:EzLangParser.ParamContext):
        pass

    # Exit a parse tree produced by EzLangParser#param.
    def exitParam(self, ctx:EzLangParser.ParamContext):
        pass


    # Enter a parse tree produced by EzLangParser#block.
    def enterBlock(self, ctx:EzLangParser.BlockContext):
        pass

    # Exit a parse tree produced by EzLangParser#block.
    def exitBlock(self, ctx:EzLangParser.BlockContext):
        pass


    # Enter a parse tree produced by EzLangParser#flowBlock.
    def enterFlowBlock(self, ctx:EzLangParser.FlowBlockContext):
        pass

    # Exit a parse tree produced by EzLangParser#flowBlock.
    def exitFlowBlock(self, ctx:EzLangParser.FlowBlockContext):
        pass


    # Enter a parse tree produced by EzLangParser#matchBlock.
    def enterMatchBlock(self, ctx:EzLangParser.MatchBlockContext):
        pass

    # Exit a parse tree produced by EzLangParser#matchBlock.
    def exitMatchBlock(self, ctx:EzLangParser.MatchBlockContext):
        pass


    # Enter a parse tree produced by EzLangParser#matchClause.
    def enterMatchClause(self, ctx:EzLangParser.MatchClauseContext):
        pass

    # Exit a parse tree produced by EzLangParser#matchClause.
    def exitMatchClause(self, ctx:EzLangParser.MatchClauseContext):
        pass


    # Enter a parse tree produced by EzLangParser#catchBlock.
    def enterCatchBlock(self, ctx:EzLangParser.CatchBlockContext):
        pass

    # Exit a parse tree produced by EzLangParser#catchBlock.
    def exitCatchBlock(self, ctx:EzLangParser.CatchBlockContext):
        pass


    # Enter a parse tree produced by EzLangParser#ifLikeExpr.
    def enterIfLikeExpr(self, ctx:EzLangParser.IfLikeExprContext):
        pass

    # Exit a parse tree produced by EzLangParser#ifLikeExpr.
    def exitIfLikeExpr(self, ctx:EzLangParser.IfLikeExprContext):
        pass


    # Enter a parse tree produced by EzLangParser#loopExpr.
    def enterLoopExpr(self, ctx:EzLangParser.LoopExprContext):
        pass

    # Exit a parse tree produced by EzLangParser#loopExpr.
    def exitLoopExpr(self, ctx:EzLangParser.LoopExprContext):
        pass


    # Enter a parse tree produced by EzLangParser#statement.
    def enterStatement(self, ctx:EzLangParser.StatementContext):
        pass

    # Exit a parse tree produced by EzLangParser#statement.
    def exitStatement(self, ctx:EzLangParser.StatementContext):
        pass


    # Enter a parse tree produced by EzLangParser#expressionStatement.
    def enterExpressionStatement(self, ctx:EzLangParser.ExpressionStatementContext):
        pass

    # Exit a parse tree produced by EzLangParser#expressionStatement.
    def exitExpressionStatement(self, ctx:EzLangParser.ExpressionStatementContext):
        pass


    # Enter a parse tree produced by EzLangParser#returnStatement.
    def enterReturnStatement(self, ctx:EzLangParser.ReturnStatementContext):
        pass

    # Exit a parse tree produced by EzLangParser#returnStatement.
    def exitReturnStatement(self, ctx:EzLangParser.ReturnStatementContext):
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


    # Enter a parse tree produced by EzLangParser#throwStatement.
    def enterThrowStatement(self, ctx:EzLangParser.ThrowStatementContext):
        pass

    # Exit a parse tree produced by EzLangParser#throwStatement.
    def exitThrowStatement(self, ctx:EzLangParser.ThrowStatementContext):
        pass



del EzLangParser