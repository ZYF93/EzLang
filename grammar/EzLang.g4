grammar EzLang;

// ==================== 词法规则 ====================

// 关键字
LET: 'let';
CONST: 'const';
STATIC: 'static';
STRUCT: 'struct';
TYPE: 'type';
DECLARE: 'declare';
LOOP: 'loop';
BREAK: 'break';
CONTINUE: 'continue';
IMPORT: 'import';
EXPORT: 'export';
FROM: 'from';
MATCH: 'match';
CATCH: 'catch';
THROW: 'throw';
FLOW: 'flow';
TYPEOF: 'typeof';
RETURN: 'return';
IN: 'in';
FOR: 'for';

// 基本类型
I8: 'I8';
I32: 'I32';
I64: 'I64';
U8: 'U8';
U32: 'U32';
U64: 'U64';
F32: 'F32';
F64: 'F64';
STR: 'Str';
BOOL: 'Bool';
VOID: 'Void';
VEC: 'Vec';
LIST: 'List';

// 目标平台
LINUX: 'linux';
MACOS: 'macos';
WINDOWS: 'windows';
ANDROID: 'android';
IOS: 'ios';
EMCC: 'emcc';

// 标识符
IDENTIFIER: [a-zA-Z_] [a-zA-Z0-9_]*;

// 字面量
INTEGER_LITERAL: '-'? (DECIMAL | BINARY | OCTAL | HEX);
FLOAT_LITERAL: '-'? (DECIMAL '.' DECIMAL? EXPONENT? | DECIMAL EXPONENT);
STRING_LITERAL: '"' (~["\\\r\n] | '\\' .)* '"';
BOOL_LITERAL: 'true' | 'false';

// 标点符号
LPAREN: '(';
RPAREN: ')';
LBRACE: '{';
RBRACE: '}';
LBRACK: '[';
RBRACK: ']';
LANGLE: '<';
RANGLE: '>';
SEMI: ';';
COLON: ':';
COMMA: ',';
DOT: '.';
ASSIGN: '=';
QUESTION: '?';
BANG: '!';
AT: '@';
AMPERSAND: '&';
PIPE: '|';
CARET: '^';
TILDE: '~';
PLUS: '+';
MINUS: '-';
STAR: '*';
SLASH: '/';
PERCENT: '%';
EQ: '==';
NE: '!=';
LE: '<=';
GE: '>=';
SHL: '<<';
SHR: '>>';
AND: '&&';
OR: '||';
PLUS_ASSIGN: '+=';
MINUS_ASSIGN: '-=';
STAR_ASSIGN: '*=';
SLASH_ASSIGN: '/=';
PERCENT_ASSIGN: '%=';
AMPERSAND_ASSIGN: '&=';
PIPE_ASSIGN: '|=';
CARET_ASSIGN: '^=';
SHL_ASSIGN: '<<=';
SHR_ASSIGN: '>>=';
ARROW: '->';
ELLIPSIS: '...';
SPREAD: '...';

// 注释
LINE_COMMENT: '//' ~[\r\n]* -> channel(HIDDEN);
BLOCK_COMMENT: '/*' .*? '*/' -> channel(HIDDEN);

// 空白字符
WS: [ \t\r\n]+ -> skip;

// 片段
fragment DECIMAL: [0-9][0-9_]*;
fragment BINARY: '0b' [01][01_]*;
fragment OCTAL: '0o' [0-7][0-7_]*;
fragment HEX: '0x' [0-9a-fA-F][0-9a-fA-F_]*;
fragment EXPONENT: [eE] [+-]? [0-9][0-9_]*;

// ==================== 语法规则 ====================

// 编译单元
compilationUnit: (statement | declaration | externDecl)* EOF;

// 声明
declaration:
    variableDecl
    | structDecl
    | typeAliasDecl
    | functionDecl
    | importDecl
    | exportDecl
    | declareDecl;

// 变量声明
variableDecl: (LET | CONST | STATIC) IDENTIFIER (':' type_)? ASSIGN expression ';'?;

// 结构体声明
structDecl:
    STRUCT IDENTIFIER genericParams? '{' structMember* '}';

structMember:
    structField
    | structMethod
    | structSpread;

structSpread: ELLIPSIS type_ ';'?;

structField:
    IDENTIFIER ':' type_ (ASSIGN expression)? ';'?;

structMethod:
    IDENTIFIER ASSIGN functionLiteral ';'?;

// 类型别名
typeAliasDecl:
    TYPE IDENTIFIER genericParams? ASSIGN typeShape ';'?;

typeShape: '{' (typeShapeMember | typeShapeSpread)* '}';

typeShapeMember:
    (IDENTIFIER | '[' IDENTIFIER ':' type_ ']') ':' type_ ';'?;

typeShapeSpread: ELLIPSIS type_ ';'?;

// 函数声明
functionDecl:
    (LET | CONST) IDENTIFIER genericParams? ASSIGN functionLiteral ';'?;

// 导入导出
importDecl:
    FROM STRING_LITERAL IMPORT '{' importSpecList? '}' ';'?;

importSpecList:
    importSpec (',' importSpec)* ','?;

importSpec:
    IDENTIFIER (AS IDENTIFIER)?;

exportDecl:
    EXPORT (variableDecl | structDecl | typeAliasDecl | functionDecl);

// extern 声明
externDecl:
    EXTERN STRING_LITERAL (FOR targetPlatform)? ';'?;

targetPlatform:
    LINUX | MACOS | WINDOWS | ANDROID | IOS | EMCC;

// declare 声明
declareDecl:
    DECLARE (LET | CONST | STATIC) IDENTIFIER ':' type_ ';'?;

// ==================== 类型 ====================

type_:
    type_ QUESTION                           # optionalType
    | type_ PIPE type_                       # unionType
    | type_ '[' ']'                          # arrayType
    | VEC '<' type_ '>' '[' INTEGER_LITERAL ']'  # vecType
    | LIST '<' type_ '>'                     # listType
    | functionType                           # functionTypeRef
    | LANGLE typeList RANGLE '=>' type_      # genericFunctionType
    | baseType                               # baseTypeRef
    | TYPEOF expression                      # typeofType
    | '(' type_ ')'                          # parenType;

baseType:
    I8 | I32 | I64 | U8 | U32 | U64 | F32 | F64 | STR | BOOL | VOID
    | IDENTIFIER genericArgs?;

genericParams: LANGLE IDENTIFIER (',' IDENTIFIER)* RANGLE;

genericArgs: LANGLE type_ (',' type_)* RANGLE;

typeList: type_ (',' type_)*;

functionType:
    '(' paramTypeList? ')' ARROW type_;

paramTypeList:
    paramType (',' paramType)* ','?;

paramType:
    IDENTIFIER ':' type_;

// ==================== 表达式 ====================

expression:
    lambdaExpression;

lambdaExpression:
    conditionalExpression;

// 条件表达式
conditionalExpression:
    orExpression (QUESTION orExpression COLON orExpression)?;

orExpression:
    andExpression (OR andExpression)*;

andExpression:
    bitOrExpression (AND bitOrExpression)*;

bitOrExpression:
    bitXorExpression (PIPE bitXorExpression)*;

bitXorExpression:
    bitAndExpression (CARET bitAndExpression)*;

bitAndExpression:
    equalityExpression (AMPERSAND equalityExpression)*;

equalityExpression:
    relationalExpression ((EQ | NE) relationalExpression)*;

relationalExpression:
    shiftExpression ((LANGLE | RANGLE | LE | GE) shiftExpression)*;

shiftExpression:
    additiveExpression ((SHL | SHR) additiveExpression)*;

additiveExpression:
    multiplicativeExpression ((PLUS | MINUS) multiplicativeExpression)*;

multiplicativeExpression:
    unaryExpression ((STAR | SLASH | PERCENT) unaryExpression)*;

// 一元表达式
unaryExpression:
    (BANG | MINUS | PLUS | TILDE) unaryExpression
    | postfixExpression;

// 后缀表达式
postfixExpression:
    primaryExpression
    | postfixExpression '.' IDENTIFIER               # memberAccess
    | postfixExpression '(' namedArgList? ')'       # call
    | postfixExpression '[' expression ']'          # index
    | postfixExpression BANG                        # typeAssertion
    | postfixExpression QUESTION                    # optionalUnwrap
    | postfixExpression ARROW IDENTIFIER '(' pipelineArgList? ')'  # pipeline;

// 主表达式
primaryExpression:
    literal
    | IDENTIFIER genericArgs?
    | '(' expression ')'
    | block
    | structLiteral
    | arrayLiteral
    | vecLiteral
    | functionLiteral
    | flowBlock
    | matchBlock
    | catchBlock
    | loopExpr
    | ifLikeExpr;

// 字面量
literal:
    INTEGER_LITERAL
    | FLOAT_LITERAL
    | STRING_LITERAL
    | BOOL_LITERAL;

// 具名参数列表
namedArgList:
    namedArg (',' namedArg)* ','?;

namedArg:
    IDENTIFIER '=' expression;

// 管道参数列表
pipelineArgList:
    pipelineArg (',' pipelineArg)* ','?;

pipelineArg:
    IDENTIFIER '=' (expression | '%');

// 结构体字面量
structLiteral:
    IDENTIFIER genericArgs? '(' structFieldInitList? ')';

structFieldInitList:
    structFieldInit (',' structFieldInit)* ','?;

structFieldInit:
    ELLIPSIS expression
    | IDENTIFIER '=' expression;

// 数组字面量
arrayLiteral:
    '[' expressionList? ']';

// SIMD 向量字面量
vecLiteral:
    VEC '[' expressionList? ']';

expressionList:
    expression (',' expression)* ','?;

// 函数字面量
functionLiteral:
    genericParams? '(' paramList? ')' (':' type_)? ARROW (expression | block);

paramList:
    param (',' param)* ','?;

param:
    IDENTIFIER ':' type_ (ASSIGN expression)?;

// 块
block:
    '{' statement* '}';

// flow 块
flowBlock:
    FLOW block;

// match 块
matchBlock:
    MATCH '{' matchClause* '}';

matchClause:
    '(' expression ')' QUESTION (expression | block) ','?;

// catch 块
catchBlock:
    CATCH block;

// 类 if 表达式
ifLikeExpr:
    '(' expression ')' QUESTION (expression | block) (COLON (expression | block))?;

// 循环表达式
loopExpr:
    LOOP (IDENTIFIER IN expression)? block;

// ==================== 语句 ====================

statement:
    declaration
    | expressionStatement
    | assignmentStatement
    | returnStatement
    | breakStatement
    | continueStatement
    | throwStatement;

expressionStatement:
    expression ';'?;

assignmentStatement:
    expression assignmentOperator expression ';'?;

assignmentOperator:
    ASSIGN | PLUS_ASSIGN | MINUS_ASSIGN | STAR_ASSIGN | SLASH_ASSIGN
    | PERCENT_ASSIGN | AMPERSAND_ASSIGN | PIPE_ASSIGN | CARET_ASSIGN
    | SHL_ASSIGN | SHR_ASSIGN;

returnStatement:
    RETURN expression? ';'?;

breakStatement:
    BREAK ';'?;

continueStatement:
    CONTINUE ';'?;

throwStatement:
    THROW expression ';'?;
