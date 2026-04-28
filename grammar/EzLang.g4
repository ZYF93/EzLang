grammar EzLang;

// ======================== Parser Rules ========================

program
    : topLevelStatement* EOF
    ;

topLevelStatement
    : statement
    ;

statement
    : letDecl
    | constDecl
    | staticDecl
    | structDef
    | typeDef
    | declareStmt
    | importStmt
    | exportStmt
    | returnStmt
    | throwStmt
    | breakStmt
    | continueStmt
    | loopStmt
    | matchStmt
    | condBlockStmt
    | exprStmt
    ;

// ---- Declarations ----

letDecl
    : decorator? LET IDENT (COLON typeExpr)? ASSIGN expression SEMI
    ;

constDecl
    : decorator? ASYNC? CONST IDENT (COLON typeExpr)? ASSIGN expression SEMI
    ;

staticDecl
    : STATIC IDENT (COLON typeExpr)? ASSIGN expression SEMI
    ;

// ---- Struct ----

structDef
    : STRUCT IDENT typeParams? LBRACE structMember* RBRACE SEMI?
    ;

structMember
    : DOTDOTDOT IDENT SEMI                              // ...Base;
    | IDENT COLON typeExpr (ASSIGN expression)? SEMI  // field: Type = default;
    | IDENT ASSIGN expression SEMI                    // method = expr;
    ;

// ---- Type Alias ----

typeDef
    : TYPE IDENT typeParams? ASSIGN shapeType SEMI?
    | TYPE IDENT typeParams? ASSIGN typeExpr SEMI?
    ;

shapeType
    : LBRACE shapeMember* RBRACE
    ;

shapeMember
    : DOTDOTDOT IDENT SEMI                                              // ...Base;
    | LBRACKET IDENT COLON typeExpr RBRACKET COLON typeExpr SEMI?    // [key: KType]: VType
    | IDENT COLON typeExpr SEMI                                      // field: Type;
    ;

// ---- Declare / Import / Export ----

declareStmt
    : DECLARE CONST IDENT COLON typeExpr SEMI
    ;

importStmt
    : FROM STRING IMPORT LBRACE importItem (COMMA importItem)* RBRACE SEMI?
    ;

importItem
    : IDENT (AS IDENT)?
    ;

exportStmt
    : EXPORT letDecl
    | EXPORT constDecl
    | EXPORT staticDecl
    ;

// ---- Control Statements ----

returnStmt
    : RETURN expression? SEMI
    ;

throwStmt
    : THROW expression SEMI
    ;

breakStmt
    : BREAK SEMI?
    ;

continueStmt
    : CONTINUE SEMI?
    ;

exprStmt
    : expression SEMI
    ;

loopStmt
    : loopExpr SEMI?
    ;

matchStmt
    : matchExpr SEMI?
    ;

condBlockStmt
    : pipeExpr QUESTION block (COLON (block | conditionalExpr))? SEMI?
    ;

decorator
    : AT IDENT
    ;

// ======================== Expressions ========================

expression
    : assignExpr
    ;

assignExpr
    : conditionalExpr assignOp assignExpr     // right-associative
    | conditionalExpr
    ;

assignOp
    : ASSIGN | PLUS_ASSIGN | MINUS_ASSIGN | STAR_ASSIGN | SLASH_ASSIGN
    | PERCENT_ASSIGN | AMP_ASSIGN | PIPE_ASSIGN | CARET_ASSIGN
    | SHL_ASSIGN | SHR_ASSIGN
    ;

conditionalExpr
    : pipeExpr QUESTION block COLON conditionalExpr   // chained: (c)?{} : (c2)?{}
    | pipeExpr QUESTION block COLON block             // (c)?{} : {}
    | pipeExpr QUESTION block                         // (c)?{}
    | pipeExpr QUESTION BREAK                         // (c) ? break
    | pipeExpr QUESTION CONTINUE                      // (c) ? continue
    | pipeExpr QUESTION expression COLON expression   // ternary value
    | pipeExpr QUESTION expression                    // conditional expr
    | pipeExpr
    ;

pipeExpr
    : orExpr (PIPE_ARROW IDENT LPAREN namedArgList? RPAREN)*
    ;

orExpr
    : andExpr (OR andExpr)*
    ;

andExpr
    : bitOrExpr (AND bitOrExpr)*
    ;

bitOrExpr
    : bitXorExpr (BIT_OR bitXorExpr)*
    ;

bitXorExpr
    : bitAndExpr (CARET bitAndExpr)*
    ;

bitAndExpr
    : eqExpr (AMP eqExpr)*
    ;

eqExpr
    : compExpr ((EQUAL | NOT_EQUAL) compExpr)*
    ;

compExpr
    : shiftExpr ((LT | GT | LTE | GTE) shiftExpr)*
    ;

shiftExpr
    : addExpr ((SHL | SHR) addExpr)*
    ;

addExpr
    : mulExpr ((PLUS | MINUS) mulExpr)*
    ;

mulExpr
    : unaryExpr ((STAR | SLASH | PERCENT) unaryExpr)*
    ;

unaryExpr
    : BANG unaryExpr
    | MINUS unaryExpr
    | postfixExpr
    ;

postfixExpr
    : primaryExpr postfix*
    ;

postfix
    : DOT IDENT                           // member access
    | LPAREN namedArgList? RPAREN         // function/struct call
    | LBRACKET expression RBRACKET        // index
    ;

primaryExpr
    : INT_LIT
    | FLOAT_LIT
    | STRING
    | BOOL_LIT
    | IDENT typeArgs?
    | LPAREN expression RPAREN
    | block
    | lambdaExpr
    | matchExpr
    | loopExpr
    | catchExpr
    | arrayLiteral
    | vecLiteral
    | dictLiteral
    | typeofExpr
    | AWAIT expression
    ;

// ---- Lambda ----

lambdaExpr
    : typeParams? LPAREN paramList? RPAREN (COLON typeExpr)? FAT_ARROW expression
    | typeParams? LPAREN paramList? RPAREN (COLON typeExpr)? FAT_ARROW block
    ;

paramList
    : param (COMMA param)*
    ;

param
    : IDENT COLON typeExpr (ASSIGN expression)?
    ;

// ---- Named arguments ----

namedArgList
    : namedArg (COMMA namedArg)*
    ;

namedArg
    : IDENT ASSIGN expression             // name = value
    | IDENT ASSIGN QUESTION               // currying placeholder
    | DOTDOTDOT expression                   // ...obj
    ;

// ---- Block ----

block
    : LBRACE statement* RBRACE
    ;

// ---- Match ----

matchExpr
    : MATCH LBRACE matchArm (COMMA matchArm)* COMMA? RBRACE
    ;

matchArm
    : LPAREN expression RPAREN QUESTION block
    | LPAREN expression RPAREN QUESTION expression
    ;

// ---- Loop ----

loopExpr
    : LOOP IDENT IN expression DOTDOTDOT expression block
    | LOOP block
    ;

// ---- Catch ----

catchExpr
    : CATCH block
    ;

// ---- Literals ----

arrayLiteral
    : LBRACKET (expression (COMMA expression)*)? RBRACKET
    ;

vecLiteral
    : VEC LBRACKET expression (COMMA expression)* RBRACKET
    ;

dictLiteral
    : LBRACE dictEntry (COMMA dictEntry)* COMMA? RBRACE
    ;

dictEntry
    : IDENT COLON typeExpr ASSIGN expression    // prop: Type = value
    | IDENT ASSIGN expression                   // prop = value (inferred)
    ;

typeofExpr
    : TYPEOF expression
    ;

// ======================== Type Expressions ========================

typeExpr
    : unionType
    ;

unionType
    : optionalType (BIT_OR optionalType)*
    ;

optionalType
    : arrayType QUESTION        // Type?
    | arrayType
    ;

arrayType
    : atomicType LBRACKET RBRACKET   // Type[]
    | atomicType
    ;

atomicType
    : IDENT typeArgs?                                       // Named type
    | VEC LT typeExpr GT LBRACKET INT_LIT RBRACKET          // Vec<T>[N]
    | LPAREN paramTypeList? RPAREN FAT_ARROW typeExpr       // Function type
    | STAR IDENT                                            // Pointer *I8
    | shapeType                                             // Inline shape
    ;

paramTypeList
    : paramType (COMMA paramType)*
    ;

paramType
    : IDENT COLON typeExpr
    ;

typeParams
    : LT IDENT (COMMA IDENT)* GT
    ;

typeArgs
    : LT typeExpr (COMMA typeExpr)* GT
    ;

// ======================== Lexer Rules ========================

// Keywords
LET         : 'let';
CONST       : 'const';
STATIC      : 'static';
STRUCT      : 'struct';
TYPE        : 'type';
DECLARE     : 'declare';
LOOP        : 'loop';
AWAIT       : 'await';
ASYNC       : 'async';
BREAK       : 'break';
CONTINUE    : 'continue';
IMPORT      : 'import';
EXPORT      : 'export';
FROM        : 'from';
MATCH       : 'match';
CATCH       : 'catch';
THROW       : 'throw';
TYPEOF      : 'typeof';
RETURN      : 'return';
IN          : 'in';
AS          : 'as';
VEC         : 'Vec';

// Boolean literals
BOOL_LIT    : 'true' | 'false';

// Operators & Punctuation
FAT_ARROW   : '=>';
PIPE_ARROW  : '->';
DOTDOTDOT   : '...';
SHL_ASSIGN  : '<<=';
SHR_ASSIGN  : '>>=';
PLUS_ASSIGN : '+=';
MINUS_ASSIGN: '-=';
STAR_ASSIGN : '*=';
SLASH_ASSIGN: '/=';
PERCENT_ASSIGN: '%=';
AMP_ASSIGN  : '&=';
PIPE_ASSIGN : '|=';
CARET_ASSIGN: '^=';
SHL         : '<<';
SHR         : '>>';
EQUAL       : '==';
NOT_EQUAL   : '!=';
LTE         : '<=';
GTE         : '>=';
AND         : '&&';
OR          : '||';
LT          : '<';
GT          : '>';
ASSIGN      : '=';
PLUS        : '+';
MINUS       : '-';
STAR        : '*';
SLASH       : '/';
PERCENT     : '%';
AMP         : '&';
BIT_OR      : '|';
CARET       : '^';
BANG        : '!';
QUESTION    : '?';
COLON       : ':';
SEMI        : ';';
COMMA       : ',';
DOT         : '.';
AT          : '@';
LPAREN      : '(';
RPAREN      : ')';
LBRACE      : '{';
RBRACE      : '}';
LBRACKET    : '[';
RBRACKET    : ']';

// Identifiers
IDENT       : [a-zA-Z_][a-zA-Z0-9_]*;

// Numeric literals
INT_LIT     : '0x' [0-9a-fA-F]+
            | '0b' [01]+
            | [0-9]+
            ;

FLOAT_LIT   : [0-9]+ '.' [0-9]+;

// String literal
STRING      : '"' (~["\\\r\n] | '\\' .)* '"';

// Whitespace & Comments
WS          : [ \t\r\n]+ -> skip;
LINE_COMMENT: '//' ~[\r\n]* -> skip;
BLOCK_COMMENT: '/*' .*? '*/' -> skip;
