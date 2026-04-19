grammar EzLang;

// Parser Rules
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

typeDeclaration : 'type' ID genericParams? '=' type ';';

variableDeclaration : decorator? ('let' | 'const' | 'static') ID genericParams? (':' type)? '=' expression ';';

structDeclaration : 'struct' ID genericParams? '{' structBody '}' ';';

structBody : (baseStruct | field | method)*;

baseStruct : '...' ID ';';

field : ID ':' type ('=' expression)? ';';

method : ID '=' functionExpression ';';

functionDeclaration : ('async')? 'const' ID '=' functionExpression ';';

functionExpression : '(' parameters? ')' ('=>' type)? blockOrExpression;

parameters : parameter (',' parameter)*;

parameter : ID (QMARK)? ':' type ('=' expression)?;

blockOrExpression : block | '=>' expression;

block : '{' statement* '}';

blockStatement : block;

importStatement : 'from' STRING 'import' '{' importItems '}' ';';

importItems : importItem (',' importItem)*;

importItem : ID ('as' ID)?;

exportStatement : 'export' (variableDeclaration | structDeclaration | functionDeclaration | typeDeclaration);

declareStatement : 'declare' ('const' | 'let' | 'static')? ID ':' type ';';

expression : pipelineExpression;

pipelineExpression : conditionalExpression (PIPE ID LPAREN argumentList? RPAREN)*;

assignmentExpression : conditionalExpression (assignmentOp conditionalExpression)*;

assignmentOp : '=' | '+=' | '-=' | '*=' | '/=' | '%=' | '&=' | '|=' | '^=' | '<<=' | '>>=';

conditionalExpression : logicalOrExpression ('?' expression ':' expression)?;

logicalOrExpression : logicalAndExpression ('||' logicalAndExpression)*;

logicalAndExpression : equalityExpression ('&&' equalityExpression)*;

equalityExpression : relationalExpression (equalityOp relationalExpression)*;

equalityOp : '==' | '!=';

relationalExpression : shiftExpression (relationalOp shiftExpression)*;

relationalOp : '<' | '>' | '<=' | '>=';

shiftExpression : additiveExpression (shiftOp additiveExpression)*;

shiftOp : '<<' | '>>';

additiveExpression : multiplicativeExpression (addOp multiplicativeExpression)*;

addOp : '+' | '-';

multiplicativeExpression : unaryExpression (mulOp unaryExpression)*;

mulOp : '*' | '/' | '%';

unaryExpression : ('+' | '-' | '!' | '~') unaryExpression | postfixExpression;

postfixExpression : primaryExpression (postfix)*;

postfix : '.' ID
        | '(' argumentList? ')'
        | '[' expression ']'
        | '!'  // type assertion
        ;

argumentList : namedArgument (',' namedArgument)*;

namedArgument : ID '=' expression | expression;

primaryExpression : literal
                  | ID
                  | '(' expression ')'
                  | vectorLiteral
                  | structLiteral
                  | markupLiteral
                  | 'typeof' '(' expression ')'
                  | 'catch' block
                  | 'throw' expression
                  | 'await' expression
                  ;

literal : INT | FLOAT | STRING | 'true' | 'false';

vectorLiteral : 'Vec' (LT simpleType GT)? LBRACK expression (COMMA expression)* RBRACK | 'Vec' LBRACK expression (COMMA expression)* RBRACK;

structLiteral : ID genericArgs? '(' structFields? ')';

structFields : structField (',' structField)*;

structField : ID '=' expression | '...' expression;

markupLiteral : LT ID markupAttrs? GT (markupContent | DIV) LT DIV ID GT | LT ID markupAttrs? DIV GT;

markupAttrs : markupAttr+;

markupAttr : ID '=' STRING | ID '=' expression;

markupContent : (STRING | LBRACE expression RBRACE | markupLiteral)*;

interpolatedString : '"' (STRING_CONTENT | '{{' expression '}}')* '"';

expressionStatement : expression ';';

// Types
type : simpleType (OR simpleType)*;

simpleType : baseType typeSuffix*;

typeSuffix : LBRACK INT? RBRACK | QMARK | LT simpleType (COMMA simpleType)* GT | LPAREN parameters? RPAREN ARROW simpleType | 'Vec' LT simpleType GT LBRACK INT RBRACK;

baseType : 'I8' | 'I32' | 'I64' | 'U8' | 'U32' | 'U64' | 'F32' | 'F64' | 'Str' | 'Bool' | 'Void' | ID;

optionalType : type '?';

unionType : type '|' type;

functionType : '(' parameters? ')' '=>' type;

genericType : ID genericArgs;

genericArgs : LT simpleType (COMMA simpleType)* GT;

genericParams : LT ID (COMMA ID)* GT;

// Decorators
decorator : '@' ID;

// Control flow
controlStatement : loopStatement | matchStatement | conditionalStatement;

loopStatement : 'loop' (rangeLoop | infiniteLoop);

infiniteLoop : block;

rangeLoop : ID 'in' expression '...' expression block;

conditionalStatement : expression '?' (expression | block) (':' (expression | block))?;

matchStatement : 'match' '{' matchCase (',' matchCase)* '}';

matchCase : '(' expression ')' '?' (expression | block);

// Lexer Rules
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
VOID : 'void';
AS : 'as';
IN : 'in';

// Operators
PLUS : '+';
MINUS : '-';
MUL : '*';
DIV : '/';
MOD : '%';
AND : '&';
OR : '|';
XOR : '^';
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

// Literals
ID : [a-zA-Z_][a-zA-Z0-9_]*;
INT : [0-9]+;
FLOAT : [0-9]+ '.' [0-9]* | '.' [0-9]+;
STRING : '"' (STRING_CONTENT | '{{' .*? '}}')* '"';
fragment STRING_CONTENT : ~["\\] | '\\' .;

// Comments
LINE_COMMENT : '//' ~[\r\n]* -> skip;
BLOCK_COMMENT : '/*' .*? '*/' -> skip;

// Whitespace
WS : [ \t\r\n]+ -> skip;