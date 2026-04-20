import sys
import os
from antlr4 import InputStream, CommonTokenStream

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from ezlang.antlr_generated.EzLangLexer import EzLangLexer
from ezlang.antlr_generated.EzLangParser import EzLangParser

def debug_tree():
    source = "let p = Point();"
    input_stream = InputStream(source)
    lexer = EzLangLexer(input_stream)
    tokens = CommonTokenStream(lexer)
    parser = EzLangParser(tokens)
    tree = parser.program()
    
    print(tree.toStringTree(recog=parser))

if __name__ == "__main__":
    debug_tree()
