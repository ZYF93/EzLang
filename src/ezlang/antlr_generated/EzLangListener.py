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


    # Enter a parse tree produced by EzLangParser#field.
    def enterField(self, ctx:EzLangParser.FieldContext):
        pass

    # Exit a parse tree produced by EzLangParser#field.
    def exitField(self, ctx:EzLangParser.FieldContext):
        pass


    # Enter a parse tree produced by EzLangParser#functionDeclaration.
    def enterFunctionDeclaration(self, ctx:EzLangParser.FunctionDeclarationContext):
        pass

    # Exit a parse tree produced by EzLangParser#functionDeclaration.
    def exitFunctionDeclaration(self, ctx:EzLangParser.FunctionDeclarationContext):
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


    # Enter a parse tree produced by EzLangParser#expressionStatement.
    def enterExpressionStatement(self, ctx:EzLangParser.ExpressionStatementContext):
        pass

    # Exit a parse tree produced by EzLangParser#expressionStatement.
    def exitExpressionStatement(self, ctx:EzLangParser.ExpressionStatementContext):
        pass


    # Enter a parse tree produced by EzLangParser#expression.
    def enterExpression(self, ctx:EzLangParser.ExpressionContext):
        pass

    # Exit a parse tree produced by EzLangParser#expression.
    def exitExpression(self, ctx:EzLangParser.ExpressionContext):
        pass


    # Enter a parse tree produced by EzLangParser#primary.
    def enterPrimary(self, ctx:EzLangParser.PrimaryContext):
        pass

    # Exit a parse tree produced by EzLangParser#primary.
    def exitPrimary(self, ctx:EzLangParser.PrimaryContext):
        pass


    # Enter a parse tree produced by EzLangParser#type.
    def enterType(self, ctx:EzLangParser.TypeContext):
        pass

    # Exit a parse tree produced by EzLangParser#type.
    def exitType(self, ctx:EzLangParser.TypeContext):
        pass


    # Enter a parse tree produced by EzLangParser#block.
    def enterBlock(self, ctx:EzLangParser.BlockContext):
        pass

    # Exit a parse tree produced by EzLangParser#block.
    def exitBlock(self, ctx:EzLangParser.BlockContext):
        pass



del EzLangParser