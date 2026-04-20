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
INT : [0-9]+ | '0x' [0-9a-fA-F]+ | '0b' [01]+;
FLOAT : [0-9]+ '.' [0-9]* | '.' [0-9]+;

// String with interpolation support
STRING : QUOTE (STRING_CONTENT | LBRACE_INTERP (options {greedy=false;} : .)* RBRACE_INTERP)* QUOTE;
fragment STRING_CONTENT : ~["\\{] | '\\' . | '{' ~['{'];

// Comments
LINE_COMMENT : '//' ~[\r\n]* -> skip;
BLOCK_COMMENT : '/*' .*? '*/' -> skip;

// Whitespace
WS : [ \t\r\n]+ -> skip;


// --- Parser Rules ---

program : statement* EOF;

statement : typeDeclaration
          | variableDeclaration
          | structDeclaration
          | functionDeclaration
          | importStatement
          | exportStatement
          | declareStatement
          | expressionStatement
          | blockStatement
          ;

typeDeclaration : TYPE ID genericParams? ASSIGN type SEMI;

variableDeclaration : decorator? (LET | CONST | STATIC) ID genericParams? (COLON type)? ASSIGN expression SEMI;

structDeclaration : STRUCT ID genericParams? LBRACE structBody RBRACE SEMI;

structBody : (baseStruct | field | method)*;

baseStruct : ELLIPSIS ID SEMI;

field : ID COLON type (ASSIGN expression)? SEMI;

method : ID ASSIGN functionExpression SEMI;

functionDeclaration : (ASYNC)? CONST ID ASSIGN functionExpression SEMI;

functionExpression : LPAREN parameters? RPAREN (ARROW type)? blockOrExpression;

parameters : parameter (COMMA parameter)*;

parameter : ID (QMARK)? COLON type (ASSIGN expression)?;

blockOrExpression : block | ARROW expression;

block : LBRACE statement* RBRACE;

blockStatement : block;

importStatement : FROM STRING IMPORT LBRACE importItems RBRACE SEMI;

importItems : importItem (COMMA importItem)*;

importItem : ID (AS ID)?;

exportStatement : EXPORT (variableDeclaration | structDeclaration | functionDeclaration | typeDeclaration);

declareStatement : DECLARE (CONST | LET | STATIC)? ID COLON type SEMI;

expression : pipelineExpression;

pipelineExpression : conditionalExpression (PIPE ID LPAREN argumentList? RPAREN)*;

assignmentExpression : conditionalExpression (assignmentOp conditionalExpression)*;

assignmentOp : ASSIGN | ADD_ASSIGN | SUB_ASSIGN | MUL_ASSIGN | DIV_ASSIGN | MOD_ASSIGN | AND_ASSIGN | OR_ASSIGN | XOR_ASSIGN | LSHIFT_ASSIGN | RSHIFT_ASSIGN;

conditionalExpression : logicalOrExpression (QMARK expression COLON expression)?;

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
                  | LPAREN expression RPAREN
                  | vectorLiteral
                  | structLiteral
                  | markupLiteral
                  | TYPEOF LPAREN expression RPAREN
                  | CATCH block
                  | THROW expression
                  | AWAIT expression
                  ;

literal : INT | FLOAT | STRING | TRUE | FALSE;

vectorLiteral : VEC_LIT (LT simpleType GT)? LBRACK expression (COMMA expression)* RBRACK | VEC_LIT LBRACK expression (COMMA expression)* RBRACK;

structLiteral : ID genericArgs? LPAREN structFields? RPAREN;

structFields : structField (COMMA structField)*;

structField : ID ASSIGN expression | ELLIPSIS expression;

markupLiteral : LT ID markupAttrs? GT (markupContent | DIV) LT DIV ID GT | LT ID markupAttrs? DIV GT;

markupAttrs : markupAttr+;

markupAttr : ID ASSIGN STRING | ID ASSIGN expression;

markupContent : (STRING | LBRACE expression RBRACE | markupLiteral)*;

interpolatedString : QUOTE (STRING_CONTENT | LBRACE_INTERP expression RBRACE_INTERP)* QUOTE;

expressionStatement : expression SEMI;

// Types
type : (functionType | simpleType) (OR (functionType | simpleType))*;

simpleType : baseType typeSuffix*;

typeSuffix : LBRACK INT? RBRACK | QMARK | LT simpleType (COMMA simpleType)* GT | LPAREN parameters? RPAREN ARROW simpleType | VEC_LIT LT simpleType GT LBRACK INT RBRACK;

baseType : I8 | I32 | I64 | U8 | U32 | U64 | F32 | F64 | STR_TYPE | BOOL_TYPE | VOID_TYPE_CAP | ID;

optionalType : type QMARK;

unionType : type OR type;

functionType : LPAREN parameters? RPAREN ARROW type;

genericType : ID genericArgs;

genericArgs : LT simpleType (COMMA simpleType)* GT;

genericParams : LT ID (COMMA ID)* GT;

// Decorators
decorator : AT ID;

// Control flow
controlStatement : loopStatement | matchStatement | conditionalStatement;

loopStatement : LOOP (rangeLoop | infiniteLoop);

infiniteLoop : block;

rangeLoop : ID IN expression ELLIPSIS expression block;

conditionalStatement : expression QMARK (expression | block) (COLON (expression | block))?;

matchStatement : MATCH LBRACE matchCase (COMMA matchCase)* RBRACE;

matchCase : LPAREN expression RPAREN QMARK (expression | block);