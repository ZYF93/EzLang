grammar EzLang;

// Parser Rules
program : statement* EOF;

statement : typeDeclaration
          | variableDeclaration
          | structDeclaration
          | functionDeclaration
          | expressionStatement
          ;

typeDeclaration : 'type' ID '=' type ';';

variableDeclaration : ('let' | 'const' | 'static') ID (':' type)? '=' expression ';';

structDeclaration : 'struct' ID '{' field* '}' ';';

field : ID ':' type ';';

functionDeclaration : 'fn' ID '(' parameters? ')' (':' type)? block;

parameters : parameter (',' parameter)*;

parameter : ID ':' type;

expressionStatement : expression ';';

expression : primary;

primary : ID | INT | STRING;

type : 'I32' | 'U32' | 'F32' | 'Str' | 'Bool' | ID;

block : '{' statement* '}';

// Lexer Rules
ID : [a-zA-Z_][a-zA-Z0-9_]*;
INT : [0-9]+;
STRING : '"' .*? '"';
WS : [ \t\r\n]+ -> skip;