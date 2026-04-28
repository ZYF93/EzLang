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


    # Visit a parse tree produced by EzLangParser#topLevelStatement.
    def visitTopLevelStatement(self, ctx:EzLangParser.TopLevelStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#statement.
    def visitStatement(self, ctx:EzLangParser.StatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#letDecl.
    def visitLetDecl(self, ctx:EzLangParser.LetDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#constDecl.
    def visitConstDecl(self, ctx:EzLangParser.ConstDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#staticDecl.
    def visitStaticDecl(self, ctx:EzLangParser.StaticDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#structDef.
    def visitStructDef(self, ctx:EzLangParser.StructDefContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#structMember.
    def visitStructMember(self, ctx:EzLangParser.StructMemberContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#typeDef.
    def visitTypeDef(self, ctx:EzLangParser.TypeDefContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#shapeType.
    def visitShapeType(self, ctx:EzLangParser.ShapeTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#shapeMember.
    def visitShapeMember(self, ctx:EzLangParser.ShapeMemberContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#declareStmt.
    def visitDeclareStmt(self, ctx:EzLangParser.DeclareStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#importStmt.
    def visitImportStmt(self, ctx:EzLangParser.ImportStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#importItem.
    def visitImportItem(self, ctx:EzLangParser.ImportItemContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#exportStmt.
    def visitExportStmt(self, ctx:EzLangParser.ExportStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#returnStmt.
    def visitReturnStmt(self, ctx:EzLangParser.ReturnStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#throwStmt.
    def visitThrowStmt(self, ctx:EzLangParser.ThrowStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#breakStmt.
    def visitBreakStmt(self, ctx:EzLangParser.BreakStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#continueStmt.
    def visitContinueStmt(self, ctx:EzLangParser.ContinueStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#exprStmt.
    def visitExprStmt(self, ctx:EzLangParser.ExprStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#loopStmt.
    def visitLoopStmt(self, ctx:EzLangParser.LoopStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#matchStmt.
    def visitMatchStmt(self, ctx:EzLangParser.MatchStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#condBlockStmt.
    def visitCondBlockStmt(self, ctx:EzLangParser.CondBlockStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#decorator.
    def visitDecorator(self, ctx:EzLangParser.DecoratorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#expression.
    def visitExpression(self, ctx:EzLangParser.ExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#assignExpr.
    def visitAssignExpr(self, ctx:EzLangParser.AssignExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#assignOp.
    def visitAssignOp(self, ctx:EzLangParser.AssignOpContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#conditionalExpr.
    def visitConditionalExpr(self, ctx:EzLangParser.ConditionalExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#pipeExpr.
    def visitPipeExpr(self, ctx:EzLangParser.PipeExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#orExpr.
    def visitOrExpr(self, ctx:EzLangParser.OrExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#andExpr.
    def visitAndExpr(self, ctx:EzLangParser.AndExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#bitOrExpr.
    def visitBitOrExpr(self, ctx:EzLangParser.BitOrExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#bitXorExpr.
    def visitBitXorExpr(self, ctx:EzLangParser.BitXorExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#bitAndExpr.
    def visitBitAndExpr(self, ctx:EzLangParser.BitAndExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#eqExpr.
    def visitEqExpr(self, ctx:EzLangParser.EqExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#compExpr.
    def visitCompExpr(self, ctx:EzLangParser.CompExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#shiftExpr.
    def visitShiftExpr(self, ctx:EzLangParser.ShiftExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#addExpr.
    def visitAddExpr(self, ctx:EzLangParser.AddExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#mulExpr.
    def visitMulExpr(self, ctx:EzLangParser.MulExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#unaryExpr.
    def visitUnaryExpr(self, ctx:EzLangParser.UnaryExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#postfixExpr.
    def visitPostfixExpr(self, ctx:EzLangParser.PostfixExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#postfix.
    def visitPostfix(self, ctx:EzLangParser.PostfixContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#primaryExpr.
    def visitPrimaryExpr(self, ctx:EzLangParser.PrimaryExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#lambdaExpr.
    def visitLambdaExpr(self, ctx:EzLangParser.LambdaExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#paramList.
    def visitParamList(self, ctx:EzLangParser.ParamListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#param.
    def visitParam(self, ctx:EzLangParser.ParamContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#namedArgList.
    def visitNamedArgList(self, ctx:EzLangParser.NamedArgListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#namedArg.
    def visitNamedArg(self, ctx:EzLangParser.NamedArgContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#block.
    def visitBlock(self, ctx:EzLangParser.BlockContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#matchExpr.
    def visitMatchExpr(self, ctx:EzLangParser.MatchExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#matchArm.
    def visitMatchArm(self, ctx:EzLangParser.MatchArmContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#loopExpr.
    def visitLoopExpr(self, ctx:EzLangParser.LoopExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#catchExpr.
    def visitCatchExpr(self, ctx:EzLangParser.CatchExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#arrayLiteral.
    def visitArrayLiteral(self, ctx:EzLangParser.ArrayLiteralContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#vecLiteral.
    def visitVecLiteral(self, ctx:EzLangParser.VecLiteralContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#dictLiteral.
    def visitDictLiteral(self, ctx:EzLangParser.DictLiteralContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#dictEntry.
    def visitDictEntry(self, ctx:EzLangParser.DictEntryContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#typeofExpr.
    def visitTypeofExpr(self, ctx:EzLangParser.TypeofExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#typeExpr.
    def visitTypeExpr(self, ctx:EzLangParser.TypeExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#unionType.
    def visitUnionType(self, ctx:EzLangParser.UnionTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#optionalType.
    def visitOptionalType(self, ctx:EzLangParser.OptionalTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#arrayType.
    def visitArrayType(self, ctx:EzLangParser.ArrayTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#atomicType.
    def visitAtomicType(self, ctx:EzLangParser.AtomicTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#paramTypeList.
    def visitParamTypeList(self, ctx:EzLangParser.ParamTypeListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#paramType.
    def visitParamType(self, ctx:EzLangParser.ParamTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#typeParams.
    def visitTypeParams(self, ctx:EzLangParser.TypeParamsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by EzLangParser#typeArgs.
    def visitTypeArgs(self, ctx:EzLangParser.TypeArgsContext):
        return self.visitChildren(ctx)



del EzLangParser