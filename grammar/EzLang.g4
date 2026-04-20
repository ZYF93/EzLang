grammar EzLang;

// --- Lexer Rules ---

// Keywords
LET : 'let';
CONST : 'const';
STATIC : 'static';
STRUCT : 'struct';
TYPE : 'type';
DECLARE : 'declare';
LOOP : 'loop';
AWAIT : 'await';
ASYNC : 'async';
BREAK : 'break';
CONTINUE : 'continue';
IMPORT : 'import';
EXPORT : 'export';
FROM : 'from';
MATCH : 'match';
CATCH : 'catch';
THROW : 'throw';
TYPEOF : 'typeof';
FN : 'fn';
THIS : 'this';
TRUE : 'true';
FALSE : 'false';
VOID_TYPE : 'void';
AS : 'as';
IN : 'in';

// Type Names
I8 : 'I8';
I32 : 'I32';
I64 : 'I64';
U8 : 'U8';
U32 : 'U32';
U64 : 'U64';
F32 : 'F32';
F64 : 'F64';
STR_TYPE : 'Str';
BOOL_TYPE : 'Bool';
VOID_TYPE_CAP : 'Void';
VEC_LIT : 'Vec';

// Operators & Punctuation
ADD_ASSIGN : '+=';
SUB_ASSIGN : '-=';
MUL_ASSIGN : '*=';
DIV_ASSIGN : '/=';
MOD_ASSIGN : '%=';
AND_ASSIGN : '&=';
OR_ASSIGN : '|=';
XOR_ASSIGN : '^=';
LSHIFT_ASSIGN : '<<=';
RSHIFT_ASSIGN : '>>=';

PLUS : '+';
MINUS : '-';
MUL : '*';
DIV : '/';
MOD : '%';
AND : '&';
OR : '|';
XOR : '^';
BIT_NOT : '~';
LSHIFT : '<<';
RSHIFT : '>>';
LAND : '&&';
LOR : '||';
NOT : '!';
EQ : '==';
NE : '!=';
LT : '<';
GT : '>';
LE : '<=';
GE : '>=';
ASSIGN : '=';
QMARK : '?';
COLON : ':';
SEMI : ';';
COMMA : ',';
DOT : '.';
LPAREN : '(';
RPAREN : ')';
LBRACK : '[';
RBRACK : ']';
LBRACE : '{';
RBRACE : '}';
AT : '@';
ARROW : '=>';
PIPE : '->';
ELLIPSIS : '...';

LBRACE_INTERP : '{{';
RBRACE_INTERP : '}}';
QUOTE : '"';

// Literals
ID : [a-zA-Z_][a-zA-Z0-9_]*;
INT : '0x' [0-9a-fA-F]+ | '0b' [01]+ | [0-9]+;
FLOAT : [0-9]+ '.' [0-9]+;

// String
STRING : QUOTE (STRING_CONTENT | LBRACE_INTERP .*? RBRACE_INTERP)* QUOTE;
fragment STRING_CONTENT : ~["\\{] | '\\' . | '{' ~['{'];

// Comments
LINE_COMMENT : '//' ~[\r\n]* -> skip;
BLOCK_COMMENT : '/*' .*? '*/' -> skip;

// Whitespace
WS : [ \t\r\n]+ -> skip;


// --- Parser Rules ---

program : (statement | SEMI)* EOF;

statement : typeDeclaration
          | variableDeclaration
          | structDeclaration
          | functionDeclaration
          | importStatement
          | exportStatement
          | declareStatement
          | controlStatement
          | expressionStatement
          | blockStatement
          | breakStatement
          | continueStatement
          ;

typeDeclaration : TYPE ID genericParams? ASSIGN (type | anonymousStruct) SEMI;

anonymousStruct : LBRACE field* RBRACE;

variableDeclaration : decorator? (LET | CONST | STATIC) ID genericParams? (COLON type)? (ASSIGN expression)? SEMI;

structDeclaration : STRUCT ID genericParams? LBRACE structBody RBRACE SEMI?;

structBody : (baseStruct | field | method)*;

baseStruct : ELLIPSIS ID SEMI;

field : ID COLON type (ASSIGN expression)? SEMI;

method : ID ASSIGN functionExpression SEMI?;

functionDeclaration : (ASYNC)? CONST ID ASSIGN functionExpression SEMI?;

functionExpression : LPAREN parameters? RPAREN (ARROW type)? (block | ARROW (expression | controlFlowOnly));

parameters : parameter (COMMA parameter)*;

parameter : (THIS | ID) (QMARK)? COLON type (ASSIGN expression)?;

block : LBRACE statement* RBRACE;

blockStatement : block;

breakStatement : BREAK SEMI?;
continueStatement : CONTINUE SEMI?;

importStatement : FROM STRING IMPORT LBRACE importItems RBRACE SEMI;

importItems : importItem (COMMA importItem)*;

importItem : ID (AS ID)?;

exportStatement : EXPORT (variableDeclaration | structDeclaration | functionDeclaration | typeDeclaration);

declareStatement : DECLARE (CONST | LET | STATIC)? ID COLON type SEMI;

expression : assignmentExpression;

assignmentExpression : pipelineExpression (assignmentOp assignmentExpression)?;

assignmentOp : ASSIGN | ADD_ASSIGN | SUB_ASSIGN | MUL_ASSIGN | DIV_ASSIGN | MOD_ASSIGN | AND_ASSIGN | OR_ASSIGN | XOR_ASSIGN | LSHIFT_ASSIGN | RSHIFT_ASSIGN;

pipelineExpression : conditionalExpression (PIPE ID LPAREN argumentList? RPAREN)*;

// 修改 conditionalExpression 以支持 break/continue/throw
conditionalExpression : logicalOrExpression (QMARK (expression | block | controlFlowOnly) (COLON (expression | block | controlFlowOnly))?)?;

// 仅能在控制流中使用的特殊表达式（模拟语句行为）
controlFlowOnly : BREAK | CONTINUE | throwExpression;

logicalOrExpression : logicalAndExpression (LOR logicalAndExpression)*;

logicalAndExpression : equalityExpression (LAND equalityExpression)*;

equalityExpression : relationalExpression (equalityOp relationalExpression)*;

equalityOp : EQ | NE;

relationalExpression : shiftExpression (relationalOp shiftExpression)*;

relationalOp : LT | GT | LE | GE;

shiftExpression : additiveExpression (shiftOp additiveExpression)*;

shiftOp : LSHIFT | RSHIFT;

additiveExpression : multiplicativeExpression (addOp multiplicativeExpression)*;

addOp : PLUS | MINUS;

multiplicativeExpression : unaryExpression (mulOp unaryExpression)*;

mulOp : MUL | DIV | MOD;

unaryExpression : (PLUS | MINUS | NOT | BIT_NOT) unaryExpression | postfixExpression;

postfixExpression : primaryExpression (postfix)*;

postfix : DOT ID
        | LPAREN argumentList? RPAREN
        | LBRACK expression RBRACK
        | NOT
        ;

argumentList : namedArgument (COMMA namedArgument)*;

namedArgument : ID ASSIGN expression | expression;

primaryExpression : literal
                  | ID
                  | THIS
                  | LPAREN expression RPAREN
                  | vectorLiteral
                  | structLiteral
                  | markupLiteral
                  | TYPEOF LPAREN expression RPAREN
                  | catchExpression
                  | throwExpression
                  | awaitExpression
                  | functionExpression
                  | block
                  ;

catchExpression : CATCH block;
throwExpression : THROW expression;
awaitExpression : AWAIT expression;

literal : INT | FLOAT | STRING | TRUE | FALSE;

vectorLiteral : VEC_LIT (LT simpleType GT)? LBRACK expression (COMMA expression)* RBRACK | VEC_LIT LBRACK expression (COMMA expression)* RBRACK;

structLiteral : ID genericArgs? LPAREN structFields? RPAREN;

structFields : structField (COMMA structField)*;

structField : ID ASSIGN expression | ELLIPSIS expression;

markupLiteral : LT ID markupAttrs? GT (markupContent | DIV) LT DIV ID GT | LT ID markupAttrs? DIV GT;

markupAttrs : markupAttr+;

markupAttr : ID ASSIGN STRING | ID ASSIGN expression;

markupContent : (STRING | LBRACE expression RBRACE | markupLiteral)*;

expressionStatement : (expression | controlFlowOnly) SEMI?;

// Types
type : (functionType | simpleType) (OR (functionType | simpleType))*;

simpleType : baseType typeSuffix*;

typeSuffix : LBRACK INT? RBRACK | QMARK | LT simpleType (COMMA simpleType)* GT | LPAREN parameters? RPAREN ARROW simpleType | VEC_LIT LT simpleType GT LBRACK INT RBRACK;

// 关键修复：将 VEC_LIT 加入 baseType
baseType : I8 | I32 | I64 | U8 | U32 | U64 | F32 | F64 | STR_TYPE | BOOL_TYPE | VOID_TYPE_CAP | VEC_LIT | ID;

functionType : LPAREN parameters? RPAREN ARROW type;

genericArgs : LT simpleType (COMMA simpleType)* GT;

genericParams : LT ID (COMMA ID)* GT;

// Decorators
decorator : AT ID;

// Control flow statements
controlStatement : loopStatement | matchStatement | conditionalStatement;

loopStatement : LOOP (rangeLoop | infiniteLoop);

infiniteLoop : block;

rangeLoop : ID IN expression ELLIPSIS expression block;

conditionalStatement : expression QMARK (expression | block | controlFlowOnly) (COLON (expression | block | controlFlowOnly))?;

matchStatement : MATCH LBRACE matchCase (COMMA matchCase)* RBRACE;

matchCase : LPAREN expression RPAREN QMARK (expression | block | controlFlowOnly);