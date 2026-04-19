# Generated from grammar/EzLang.g4 by ANTLR 4.13.2
# encoding: utf-8
from antlr4 import *
from io import StringIO
import sys
if sys.version_info[1] > 5:
	from typing import TextIO
else:
	from typing.io import TextIO

def serializedATN():
    return [
        4,1,23,120,2,0,7,0,2,1,7,1,2,2,7,2,2,3,7,3,2,4,7,4,2,5,7,5,2,6,7,
        6,2,7,7,7,2,8,7,8,2,9,7,9,2,10,7,10,2,11,7,11,2,12,7,12,2,13,7,13,
        1,0,5,0,30,8,0,10,0,12,0,33,9,0,1,0,1,0,1,1,1,1,1,1,1,1,1,1,3,1,
        42,8,1,1,2,1,2,1,2,1,2,1,2,1,2,1,3,1,3,1,3,1,3,3,3,54,8,3,1,3,1,
        3,1,3,1,3,1,4,1,4,1,4,1,4,5,4,64,8,4,10,4,12,4,67,9,4,1,4,1,4,1,
        4,1,5,1,5,1,5,1,5,1,5,1,6,1,6,1,6,1,6,3,6,81,8,6,1,6,1,6,1,6,3,6,
        86,8,6,1,6,1,6,1,7,1,7,1,7,5,7,93,8,7,10,7,12,7,96,9,7,1,8,1,8,1,
        8,1,8,1,9,1,9,1,9,1,10,1,10,1,11,1,11,1,12,1,12,1,13,1,13,5,13,113,
        8,13,10,13,12,13,116,9,13,1,13,1,13,1,13,0,0,14,0,2,4,6,8,10,12,
        14,16,18,20,22,24,26,0,3,1,0,4,6,1,0,20,22,1,0,15,20,116,0,31,1,
        0,0,0,2,41,1,0,0,0,4,43,1,0,0,0,6,49,1,0,0,0,8,59,1,0,0,0,10,71,
        1,0,0,0,12,76,1,0,0,0,14,89,1,0,0,0,16,97,1,0,0,0,18,101,1,0,0,0,
        20,104,1,0,0,0,22,106,1,0,0,0,24,108,1,0,0,0,26,110,1,0,0,0,28,30,
        3,2,1,0,29,28,1,0,0,0,30,33,1,0,0,0,31,29,1,0,0,0,31,32,1,0,0,0,
        32,34,1,0,0,0,33,31,1,0,0,0,34,35,5,0,0,1,35,1,1,0,0,0,36,42,3,4,
        2,0,37,42,3,6,3,0,38,42,3,8,4,0,39,42,3,12,6,0,40,42,3,18,9,0,41,
        36,1,0,0,0,41,37,1,0,0,0,41,38,1,0,0,0,41,39,1,0,0,0,41,40,1,0,0,
        0,42,3,1,0,0,0,43,44,5,1,0,0,44,45,5,20,0,0,45,46,5,2,0,0,46,47,
        3,24,12,0,47,48,5,3,0,0,48,5,1,0,0,0,49,50,7,0,0,0,50,53,5,20,0,
        0,51,52,5,7,0,0,52,54,3,24,12,0,53,51,1,0,0,0,53,54,1,0,0,0,54,55,
        1,0,0,0,55,56,5,2,0,0,56,57,3,20,10,0,57,58,5,3,0,0,58,7,1,0,0,0,
        59,60,5,8,0,0,60,61,5,20,0,0,61,65,5,9,0,0,62,64,3,10,5,0,63,62,
        1,0,0,0,64,67,1,0,0,0,65,63,1,0,0,0,65,66,1,0,0,0,66,68,1,0,0,0,
        67,65,1,0,0,0,68,69,5,10,0,0,69,70,5,3,0,0,70,9,1,0,0,0,71,72,5,
        20,0,0,72,73,5,7,0,0,73,74,3,24,12,0,74,75,5,3,0,0,75,11,1,0,0,0,
        76,77,5,11,0,0,77,78,5,20,0,0,78,80,5,12,0,0,79,81,3,14,7,0,80,79,
        1,0,0,0,80,81,1,0,0,0,81,82,1,0,0,0,82,85,5,13,0,0,83,84,5,7,0,0,
        84,86,3,24,12,0,85,83,1,0,0,0,85,86,1,0,0,0,86,87,1,0,0,0,87,88,
        3,26,13,0,88,13,1,0,0,0,89,94,3,16,8,0,90,91,5,14,0,0,91,93,3,16,
        8,0,92,90,1,0,0,0,93,96,1,0,0,0,94,92,1,0,0,0,94,95,1,0,0,0,95,15,
        1,0,0,0,96,94,1,0,0,0,97,98,5,20,0,0,98,99,5,7,0,0,99,100,3,24,12,
        0,100,17,1,0,0,0,101,102,3,20,10,0,102,103,5,3,0,0,103,19,1,0,0,
        0,104,105,3,22,11,0,105,21,1,0,0,0,106,107,7,1,0,0,107,23,1,0,0,
        0,108,109,7,2,0,0,109,25,1,0,0,0,110,114,5,9,0,0,111,113,3,2,1,0,
        112,111,1,0,0,0,113,116,1,0,0,0,114,112,1,0,0,0,114,115,1,0,0,0,
        115,117,1,0,0,0,116,114,1,0,0,0,117,118,5,10,0,0,118,27,1,0,0,0,
        8,31,41,53,65,80,85,94,114
    ]

class EzLangParser ( Parser ):

    grammarFileName = "EzLang.g4"

    atn = ATNDeserializer().deserialize(serializedATN())

    decisionsToDFA = [ DFA(ds, i) for i, ds in enumerate(atn.decisionToState) ]

    sharedContextCache = PredictionContextCache()

    literalNames = [ "<INVALID>", "'type'", "'='", "';'", "'let'", "'const'", 
                     "'static'", "':'", "'struct'", "'{'", "'}'", "'fn'", 
                     "'('", "')'", "','", "'I32'", "'U32'", "'F32'", "'Str'", 
                     "'Bool'" ]

    symbolicNames = [ "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "ID", "INT", "STRING", "WS" ]

    RULE_program = 0
    RULE_statement = 1
    RULE_typeDeclaration = 2
    RULE_variableDeclaration = 3
    RULE_structDeclaration = 4
    RULE_field = 5
    RULE_functionDeclaration = 6
    RULE_parameters = 7
    RULE_parameter = 8
    RULE_expressionStatement = 9
    RULE_expression = 10
    RULE_primary = 11
    RULE_type = 12
    RULE_block = 13

    ruleNames =  [ "program", "statement", "typeDeclaration", "variableDeclaration", 
                   "structDeclaration", "field", "functionDeclaration", 
                   "parameters", "parameter", "expressionStatement", "expression", 
                   "primary", "type", "block" ]

    EOF = Token.EOF
    T__0=1
    T__1=2
    T__2=3
    T__3=4
    T__4=5
    T__5=6
    T__6=7
    T__7=8
    T__8=9
    T__9=10
    T__10=11
    T__11=12
    T__12=13
    T__13=14
    T__14=15
    T__15=16
    T__16=17
    T__17=18
    T__18=19
    ID=20
    INT=21
    STRING=22
    WS=23

    def __init__(self, input:TokenStream, output:TextIO = sys.stdout):
        super().__init__(input, output)
        self.checkVersion("4.13.2")
        self._interp = ParserATNSimulator(self, self.atn, self.decisionsToDFA, self.sharedContextCache)
        self._predicates = None




    class ProgramContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def EOF(self):
            return self.getToken(EzLangParser.EOF, 0)

        def statement(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.StatementContext)
            else:
                return self.getTypedRuleContext(EzLangParser.StatementContext,i)


        def getRuleIndex(self):
            return EzLangParser.RULE_program

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterProgram" ):
                listener.enterProgram(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitProgram" ):
                listener.exitProgram(self)




    def program(self):

        localctx = EzLangParser.ProgramContext(self, self._ctx, self.state)
        self.enterRule(localctx, 0, self.RULE_program)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 31
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while (((_la) & ~0x3f) == 0 and ((1 << _la) & 7342450) != 0):
                self.state = 28
                self.statement()
                self.state = 33
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 34
            self.match(EzLangParser.EOF)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class StatementContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def typeDeclaration(self):
            return self.getTypedRuleContext(EzLangParser.TypeDeclarationContext,0)


        def variableDeclaration(self):
            return self.getTypedRuleContext(EzLangParser.VariableDeclarationContext,0)


        def structDeclaration(self):
            return self.getTypedRuleContext(EzLangParser.StructDeclarationContext,0)


        def functionDeclaration(self):
            return self.getTypedRuleContext(EzLangParser.FunctionDeclarationContext,0)


        def expressionStatement(self):
            return self.getTypedRuleContext(EzLangParser.ExpressionStatementContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_statement

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterStatement" ):
                listener.enterStatement(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitStatement" ):
                listener.exitStatement(self)




    def statement(self):

        localctx = EzLangParser.StatementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 2, self.RULE_statement)
        try:
            self.state = 41
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [1]:
                self.enterOuterAlt(localctx, 1)
                self.state = 36
                self.typeDeclaration()
                pass
            elif token in [4, 5, 6]:
                self.enterOuterAlt(localctx, 2)
                self.state = 37
                self.variableDeclaration()
                pass
            elif token in [8]:
                self.enterOuterAlt(localctx, 3)
                self.state = 38
                self.structDeclaration()
                pass
            elif token in [11]:
                self.enterOuterAlt(localctx, 4)
                self.state = 39
                self.functionDeclaration()
                pass
            elif token in [20, 21, 22]:
                self.enterOuterAlt(localctx, 5)
                self.state = 40
                self.expressionStatement()
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class TypeDeclarationContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def ID(self):
            return self.getToken(EzLangParser.ID, 0)

        def type_(self):
            return self.getTypedRuleContext(EzLangParser.TypeContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_typeDeclaration

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterTypeDeclaration" ):
                listener.enterTypeDeclaration(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitTypeDeclaration" ):
                listener.exitTypeDeclaration(self)




    def typeDeclaration(self):

        localctx = EzLangParser.TypeDeclarationContext(self, self._ctx, self.state)
        self.enterRule(localctx, 4, self.RULE_typeDeclaration)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 43
            self.match(EzLangParser.T__0)
            self.state = 44
            self.match(EzLangParser.ID)
            self.state = 45
            self.match(EzLangParser.T__1)
            self.state = 46
            self.type_()
            self.state = 47
            self.match(EzLangParser.T__2)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class VariableDeclarationContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def ID(self):
            return self.getToken(EzLangParser.ID, 0)

        def expression(self):
            return self.getTypedRuleContext(EzLangParser.ExpressionContext,0)


        def type_(self):
            return self.getTypedRuleContext(EzLangParser.TypeContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_variableDeclaration

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterVariableDeclaration" ):
                listener.enterVariableDeclaration(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitVariableDeclaration" ):
                listener.exitVariableDeclaration(self)




    def variableDeclaration(self):

        localctx = EzLangParser.VariableDeclarationContext(self, self._ctx, self.state)
        self.enterRule(localctx, 6, self.RULE_variableDeclaration)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 49
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 112) != 0)):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
            self.state = 50
            self.match(EzLangParser.ID)
            self.state = 53
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==7:
                self.state = 51
                self.match(EzLangParser.T__6)
                self.state = 52
                self.type_()


            self.state = 55
            self.match(EzLangParser.T__1)
            self.state = 56
            self.expression()
            self.state = 57
            self.match(EzLangParser.T__2)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class StructDeclarationContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def ID(self):
            return self.getToken(EzLangParser.ID, 0)

        def field(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.FieldContext)
            else:
                return self.getTypedRuleContext(EzLangParser.FieldContext,i)


        def getRuleIndex(self):
            return EzLangParser.RULE_structDeclaration

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterStructDeclaration" ):
                listener.enterStructDeclaration(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitStructDeclaration" ):
                listener.exitStructDeclaration(self)




    def structDeclaration(self):

        localctx = EzLangParser.StructDeclarationContext(self, self._ctx, self.state)
        self.enterRule(localctx, 8, self.RULE_structDeclaration)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 59
            self.match(EzLangParser.T__7)
            self.state = 60
            self.match(EzLangParser.ID)
            self.state = 61
            self.match(EzLangParser.T__8)
            self.state = 65
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==20:
                self.state = 62
                self.field()
                self.state = 67
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 68
            self.match(EzLangParser.T__9)
            self.state = 69
            self.match(EzLangParser.T__2)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class FieldContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def ID(self):
            return self.getToken(EzLangParser.ID, 0)

        def type_(self):
            return self.getTypedRuleContext(EzLangParser.TypeContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_field

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterField" ):
                listener.enterField(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitField" ):
                listener.exitField(self)




    def field(self):

        localctx = EzLangParser.FieldContext(self, self._ctx, self.state)
        self.enterRule(localctx, 10, self.RULE_field)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 71
            self.match(EzLangParser.ID)
            self.state = 72
            self.match(EzLangParser.T__6)
            self.state = 73
            self.type_()
            self.state = 74
            self.match(EzLangParser.T__2)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class FunctionDeclarationContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def ID(self):
            return self.getToken(EzLangParser.ID, 0)

        def block(self):
            return self.getTypedRuleContext(EzLangParser.BlockContext,0)


        def parameters(self):
            return self.getTypedRuleContext(EzLangParser.ParametersContext,0)


        def type_(self):
            return self.getTypedRuleContext(EzLangParser.TypeContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_functionDeclaration

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterFunctionDeclaration" ):
                listener.enterFunctionDeclaration(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitFunctionDeclaration" ):
                listener.exitFunctionDeclaration(self)




    def functionDeclaration(self):

        localctx = EzLangParser.FunctionDeclarationContext(self, self._ctx, self.state)
        self.enterRule(localctx, 12, self.RULE_functionDeclaration)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 76
            self.match(EzLangParser.T__10)
            self.state = 77
            self.match(EzLangParser.ID)
            self.state = 78
            self.match(EzLangParser.T__11)
            self.state = 80
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==20:
                self.state = 79
                self.parameters()


            self.state = 82
            self.match(EzLangParser.T__12)
            self.state = 85
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==7:
                self.state = 83
                self.match(EzLangParser.T__6)
                self.state = 84
                self.type_()


            self.state = 87
            self.block()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ParametersContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def parameter(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.ParameterContext)
            else:
                return self.getTypedRuleContext(EzLangParser.ParameterContext,i)


        def getRuleIndex(self):
            return EzLangParser.RULE_parameters

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterParameters" ):
                listener.enterParameters(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitParameters" ):
                listener.exitParameters(self)




    def parameters(self):

        localctx = EzLangParser.ParametersContext(self, self._ctx, self.state)
        self.enterRule(localctx, 14, self.RULE_parameters)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 89
            self.parameter()
            self.state = 94
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==14:
                self.state = 90
                self.match(EzLangParser.T__13)
                self.state = 91
                self.parameter()
                self.state = 96
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ParameterContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def ID(self):
            return self.getToken(EzLangParser.ID, 0)

        def type_(self):
            return self.getTypedRuleContext(EzLangParser.TypeContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_parameter

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterParameter" ):
                listener.enterParameter(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitParameter" ):
                listener.exitParameter(self)




    def parameter(self):

        localctx = EzLangParser.ParameterContext(self, self._ctx, self.state)
        self.enterRule(localctx, 16, self.RULE_parameter)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 97
            self.match(EzLangParser.ID)
            self.state = 98
            self.match(EzLangParser.T__6)
            self.state = 99
            self.type_()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ExpressionStatementContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def expression(self):
            return self.getTypedRuleContext(EzLangParser.ExpressionContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_expressionStatement

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterExpressionStatement" ):
                listener.enterExpressionStatement(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitExpressionStatement" ):
                listener.exitExpressionStatement(self)




    def expressionStatement(self):

        localctx = EzLangParser.ExpressionStatementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 18, self.RULE_expressionStatement)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 101
            self.expression()
            self.state = 102
            self.match(EzLangParser.T__2)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def primary(self):
            return self.getTypedRuleContext(EzLangParser.PrimaryContext,0)


        def getRuleIndex(self):
            return EzLangParser.RULE_expression

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterExpression" ):
                listener.enterExpression(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitExpression" ):
                listener.exitExpression(self)




    def expression(self):

        localctx = EzLangParser.ExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 20, self.RULE_expression)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 104
            self.primary()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class PrimaryContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def ID(self):
            return self.getToken(EzLangParser.ID, 0)

        def INT(self):
            return self.getToken(EzLangParser.INT, 0)

        def STRING(self):
            return self.getToken(EzLangParser.STRING, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_primary

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterPrimary" ):
                listener.enterPrimary(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitPrimary" ):
                listener.exitPrimary(self)




    def primary(self):

        localctx = EzLangParser.PrimaryContext(self, self._ctx, self.state)
        self.enterRule(localctx, 22, self.RULE_primary)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 106
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 7340032) != 0)):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class TypeContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def ID(self):
            return self.getToken(EzLangParser.ID, 0)

        def getRuleIndex(self):
            return EzLangParser.RULE_type

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterType" ):
                listener.enterType(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitType" ):
                listener.exitType(self)




    def type_(self):

        localctx = EzLangParser.TypeContext(self, self._ctx, self.state)
        self.enterRule(localctx, 24, self.RULE_type)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 108
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 2064384) != 0)):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class BlockContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def statement(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(EzLangParser.StatementContext)
            else:
                return self.getTypedRuleContext(EzLangParser.StatementContext,i)


        def getRuleIndex(self):
            return EzLangParser.RULE_block

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterBlock" ):
                listener.enterBlock(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitBlock" ):
                listener.exitBlock(self)




    def block(self):

        localctx = EzLangParser.BlockContext(self, self._ctx, self.state)
        self.enterRule(localctx, 26, self.RULE_block)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 110
            self.match(EzLangParser.T__8)
            self.state = 114
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while (((_la) & ~0x3f) == 0 and ((1 << _la) & 7342450) != 0):
                self.state = 111
                self.statement()
                self.state = 116
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 117
            self.match(EzLangParser.T__9)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx





