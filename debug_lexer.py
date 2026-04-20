import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from ezlang.lexer import EzLangLexerWrapper
from ezlang.antlr_generated.EzLangLexer import EzLangLexer

def debug():
    source = "let x = 0b1010;"
    print(f"Source: {source}")
    lexer_wrapper = EzLangLexerWrapper(source)
    tokens = lexer_wrapper.get_tokens()
    
    print("\nTokens:")
    for t in tokens:
        if t.type == -1:
            print("EOF")
            continue
        
        symbolic_name = "UNKNOWN"
        if t.type < len(EzLangLexer.symbolicNames):
            symbolic_name = EzLangLexer.symbolicNames[t.type]
            
        print(f"Text: '{t.text}', Type: {t.type}, Name: {symbolic_name}")

if __name__ == "__main__":
    debug()
