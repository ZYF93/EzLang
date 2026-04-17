use std::fs;
// use inkwell::context::Context;
use ezlang::{parser, types}; // , codegen

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = std::env::args().collect();
    if args.len() != 2 {
        eprintln!("Usage: {} <file.ez>", args[0]);
        return Ok(());
    }
    let filename = &args[1];
    let source = fs::read_to_string(filename)?;

    // Parse
    let (_, stmts) = match parser::parse(&source) {
        Ok(res) => res,
        Err(e) => {
            eprintln!("Parse error: {:?}", e);
            return Ok(());
        }
    };

    // Type check
    let mut checker = types::TypeChecker::new();
    if let Err(e) = checker.check_stmts(&stmts) {
        eprintln!("Type error: {}", e);
        return Ok(());
    }

    println!("Parsed and type-checked successfully");

    // // Codegen
    // let context = Context::create();
    // let mut codegen = codegen::CodeGen::new(&context);
    // codegen.compile_stmts(&stmts)?;

    // // Write LLVM IR
    // codegen.get_module().print_to_file("output.ll")?;

    println!("Parsed and type-checked successfully");
    Ok(())
}