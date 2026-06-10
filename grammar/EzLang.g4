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
PARALLEL: 'parallel';
RP: 'rp';
WP: 'wp';
TYPEOF: 'typeof';
RETURN: 'return';
IN: 'in';
FOR: 'for';
AS: 'as';
EXTERN: 'extern';

// 基本类型关键字
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

// 字面量（BOOL_LITERAL 必须在 IDENTIFIER 之前，否则 true/false 被识别为标识符）
BOOL_LITERAL: 'true' | 'false';
INTEGER_LITERAL: DECIMAL | BINARY | OCTAL | HEX;
FLOAT_LITERAL: DECIMAL '.' DECIMAL EXPONENT? | DECIMAL EXPONENT;
STRING_LITERAL: '"' (~["\\\r\n] | '\\' .)* '"';

// 标识符（必须在所有关键字和字面量之后）
// 类型名以大写字母开头（如 User, Point），变量名以小写、下划线或 $ 开头（如 user, _count, $state）
TYPE_IDENTIFIER: [A-Z] [a-zA-Z0-9_]*;
VAR_IDENTIFIER: [a-z_] [a-zA-Z0-9_]* | '$' [a-zA-Z0-9_]+;

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
FAT_ARROW: '=>';
THIN_ARROW: '->';
ELLIPSIS: '...';

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
    functionDecl
    | variableDecl
    | structDecl
    | typeAliasDecl
    | importDecl
    | exportDecl
    | declareDecl;

// 变量声明
variableDecl: decorator* lockPrefix? (LET | CONST | STATIC) qualifiedVarName (':' type_)? (ASSIGN expression)? ';'?;

lockPrefix: RP | WP;

qualifiedVarName: VAR_IDENTIFIER (DOT VAR_IDENTIFIER)*;

decorator: AT VAR_IDENTIFIER;

// 结构体声明
structDecl:
    STRUCT TYPE_IDENTIFIER genericParams? '{' structMember* '}' ';'?;

structMember:
    structField
    | structMethod
    | structSpread;

structSpread: ELLIPSIS type_ ';'?;

structField:
    VAR_IDENTIFIER ':' type_ (ASSIGN expression)? ';'?;

structMethod:
    VAR_IDENTIFIER (ASSIGN functionLiteral | functionSignature) ';'?;

// 类型别名
typeAliasDecl:
    TYPE TYPE_IDENTIFIER genericParams? ASSIGN (typeShape | type_) ';'?;

typeShape: '{' (typeShapeMember | typeShapeSpread)* '}';

typeShapeMember:
    (VAR_IDENTIFIER | '[' VAR_IDENTIFIER ':' type_ ']') ':' type_ (ASSIGN expression)? ';'?;

typeShapeSpread: ELLIPSIS type_ ';'?;

// 函数声明
functionDecl:
    (LET | CONST) VAR_IDENTIFIER genericParams? ASSIGN functionLiteral ';'?;

// 导入导出
importDecl:
    FROM STRING_LITERAL IMPORT '{' importSpecList? '}' ';'?;

importSpecList:
    importSpec (',' importSpec)* ','?;

importSpec:
    importName (AS importName)?;

importName:
    TYPE_IDENTIFIER | VAR_IDENTIFIER;

exportDecl:
    EXPORT (functionDecl | variableDecl | structDecl | typeAliasDecl | declareDecl);

// extern 声明
externDecl:
    EXTERN STRING_LITERAL (FOR targetPlatform)? ';'?;

targetPlatform:
    LINUX | MACOS | WINDOWS | ANDROID | IOS | EMCC;

// declare 声明
declareDecl:
    DECLARE (LET | CONST | STATIC) qualifiedVarName ':' type_ ';'?;

// ==================== 类型 ====================

type_:
    type_ QUESTION                                               # optionalType
    | type_ PIPE type_                                           # unionType
    | type_ '[' ']'                                              # arrayType
    | STAR type_                                                  # pointerType
    | VEC '<' type_ '>' '[' INTEGER_LITERAL ']'                  # vecType
    | LIST '<' type_ '>'                                         # listType
    | LANGLE typeList RANGLE '(' paramTypeList? ')' FAT_ARROW type_  # genericParamFunctionType
    | functionType                                               # functionTypeRef
    | LANGLE typeList RANGLE FAT_ARROW type_                     # genericFunctionType
    | typeShape                                                  # typeShapeType
    | baseType                                                   # baseTypeRef
    | TYPEOF expression                                          # typeofType
    | '(' type_ ')'                                              # parenType;

baseType:
    I8 | I32 | I64 | U8 | U32 | U64 | F32 | F64 | STR | BOOL | VOID
    | TYPE_IDENTIFIER genericArgs?;

genericParams: LANGLE TYPE_IDENTIFIER (',' TYPE_IDENTIFIER)* RANGLE;

genericArgs: LANGLE type_ (',' type_)* RANGLE;

typeList: type_ (',' type_)*;

functionType:
    '(' paramTypeList? ')' FAT_ARROW type_;

paramTypeList:
    paramType (',' paramType)* ','?;

paramType:
    VAR_IDENTIFIER ':' type_;

// ==================== 表达式 ====================

expression:
    assignmentExpression;

assignmentExpression:
    pipelineExpression (assignmentOperator assignmentExpression)?;

assignmentOperator:
    ASSIGN | PLUS_ASSIGN | MINUS_ASSIGN | STAR_ASSIGN | SLASH_ASSIGN
    | PERCENT_ASSIGN | AMPERSAND_ASSIGN | PIPE_ASSIGN | CARET_ASSIGN
    | SHL_ASSIGN | SHR_ASSIGN;

pipelineExpression:
    conditionalExpression (THIN_ARROW VAR_IDENTIFIER genericArgs? '(' pipelineArgList? ')')?;

// 条件表达式
conditionalExpression:
    rangeExpression (QUESTION conditionalExpression COLON conditionalExpression)?;

rangeExpression:
    orExpression (ELLIPSIS orExpression)?;

orExpression:
    andExpression (OR andExpression)*;

andExpression:
    equalityExpression (AND equalityExpression)*;

equalityExpression:
    relationalExpression ((EQ | NE) relationalExpression)*;

relationalExpression:
    bitOrExpression ((LANGLE | RANGLE | LE | GE) bitOrExpression)*;

bitOrExpression:
    bitXorExpression (PIPE bitXorExpression)*;

bitXorExpression:
    bitAndExpression (CARET bitAndExpression)*;

bitAndExpression:
    shiftExpression (AMPERSAND shiftExpression)*;

shiftExpression:
    additiveExpression (shiftOperator additiveExpression)*;

shiftOperator:
    SHL | RANGLE RANGLE;

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
    primaryExpression                                                    # primaryExpr
    | postfixExpression '.' VAR_IDENTIFIER                                   # memberAccess
    | postfixExpression '(' namedArgList? ')'                           # call
    | postfixExpression '[' expression ']'                              # index
    | postfixExpression BANG                                            # typeAssertion
    | postfixExpression QUESTION                                        # optionalUnwrap
    | postfixExpression THIN_ARROW VAR_IDENTIFIER genericArgs? '(' pipelineArgList? ')'   # pipeline;

// 主表达式
// structLiteral 必须在 identifierExpr 之前，否则 Point(x=1) 会被误解析为函数调用
primaryExpression:
    literal                                                             # literalExpr
    | structLiteral                                                      # structLiteralExpr
    | (VAR_IDENTIFIER | TYPE_IDENTIFIER) genericArgs?                           # identifierExpr
    | ifLikeExpr                                                         # ifLikePrimaryExpr
    | '(' expression ')'                                                 # parenExpr
    | QUESTION                                                           # placeholderExpr
    | dictLiteral                                                        # dictExpr
    | block                                                              # blockExpr
    | arrayLiteral                                                       # arrayLiteralExpr
    | vecLiteral                                                         # vecLiteralExpr
    | functionLiteral                                                    # fnLiteralExpr
    | flowBlock                                                          # flowBlockExpr
    | parallelBlock                                                      # parallelBlockExpr
    | matchBlock                                                         # matchBlockExpr
    | catchBlock                                                         # catchBlockExpr
    | loopExpr                                                           # loopPrimaryExpr
    | typeofExpr                                                         # typeofPrimaryExpr
    | markupLiteral                                                      # markupExpr;

typeofExpr:
    TYPEOF (type_ | unaryExpression);

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
    VAR_IDENTIFIER '=' expression;

// 管道参数列表
pipelineArgList:
    pipelineArg (',' pipelineArg)* ','?;

pipelineArg:
    VAR_IDENTIFIER '=' (expression | '%');

// 结构体字面量
structLiteral:
    TYPE_IDENTIFIER genericArgs? '(' structFieldInitList? ')';

structFieldInitList:
    structFieldInit (',' structFieldInit)* ','?;

structFieldInit:
    ELLIPSIS expression
    | VAR_IDENTIFIER '=' expression;

// 字典字面量
dictLiteral:
    '{' (dictField (',' dictField)* ','?)? '}';

dictField:
    dictKey (':' type_)? ASSIGN expression;

dictKey:
    VAR_IDENTIFIER
    | STRING_LITERAL
    | LBRACK expression RBRACK;

// 数组字面量
arrayLiteral:
    '[' expressionList? ']';

// SIMD 向量字面量
vecLiteral:
    VEC '[' expressionList? ']';

expressionList:
    expression (',' expression)* ','?;

// XML 风格标记字面量
markupLiteral:
    LANGLE VAR_IDENTIFIER markupAttr* SLASH RANGLE
    | LANGLE VAR_IDENTIFIER markupAttr* RANGLE markupChild* LANGLE SLASH VAR_IDENTIFIER RANGLE;

markupAttr:
    VAR_IDENTIFIER ASSIGN (STRING_LITERAL | INTEGER_LITERAL | BOOL_LITERAL | expression);

markupChild:
    STRING_LITERAL
    | markupLiteral
    | LBRACE expression RBRACE;

// 函数字面量
functionLiteral:
    genericParams? '(' paramList? ')' (':' type_)? FAT_ARROW (expression | block);

functionSignature:
    genericParams? '(' paramList? ')' FAT_ARROW type_;

paramList:
    param (',' param)* ','?;

param:
    VAR_IDENTIFIER ':' type_ (ASSIGN expression)?;

// 块
block:
    '{' statement* '}';

// flow 块
flowBlock:
    FLOW block;

// parallel 块
parallelBlock:
    PARALLEL block;

// match 块
matchBlock:
    MATCH '{' matchClause* '}';

matchClause:
    '(' expression ')' QUESTION (statement | block) ','?;

// catch 块
catchBlock:
    CATCH block;

// 类 if 表达式
ifLikeExpr:
    '(' expression ')' QUESTION block (COLON (expression | block))?;

// 循环表达式
loopExpr:
    LOOP (VAR_IDENTIFIER IN rangeExpression)? block;

// ==================== 语句 ====================

statement:
    declaration
    | expressionStatement
    | returnStatement
    | breakStatement
    | continueStatement
    | throwStatement;

expressionStatement:
    expression ';'?;

returnStatement:
    RETURN expression? ';'?;

breakStatement:
    BREAK ';'?;

continueStatement:
    CONTINUE ';'?;

throwStatement:
    THROW expression ';'?;
