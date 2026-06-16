import * as fs from 'fs';
import * as path from 'path';
import * as vscode from 'vscode';
import { LanguageClient, LanguageClientOptions, ServerOptions } from 'vscode-languageclient/node';

let client: LanguageClient | undefined;

export function activate(context: vscode.ExtensionContext): void {
  const config = vscode.workspace.getConfiguration('ezlang');
  const customCommand = config.get<string>('server.command')?.trim();
  const customArgs = config.get<string[]>('server.args') ?? [];

  const serverOptions: ServerOptions = customCommand
    ? { command: customCommand, args: customArgs, options: { cwd: workspaceRoot() } }
    : defaultServerOptions(context);

  const clientOptions: LanguageClientOptions = {
    documentSelector: [{ scheme: 'file', language: 'ezlang' }],
    synchronize: {
      fileEvents: vscode.workspace.createFileSystemWatcher('**/*.ez')
    }
  };

  client = new LanguageClient('ezlang', 'EzLang Language Server', serverOptions, clientOptions);
  context.subscriptions.push(client);
  client.start();
}

export function deactivate(): Thenable<void> | undefined {
  return client?.stop();
}

function workspaceRoot(): string {
  return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? process.cwd();
}

function repositoryRoot(context: vscode.ExtensionContext): string {
  const fromExtension = path.resolve(context.extensionPath, '..', '..');
  if (fs.existsSync(path.join(fromExtension, 'lsp', 'server.py'))) {
    return fromExtension;
  }
  return workspaceRoot();
}

function pythonCommand(): string {
  return process.platform === 'win32' ? 'python' : 'python3';
}

function defaultServerOptions(context: vscode.ExtensionContext): ServerOptions {
  const root = repositoryRoot(context);
  if (fs.existsSync(path.join(root, 'lsp', 'server.py'))) {
    return { command: pythonCommand(), args: ['-m', 'lsp'], options: { cwd: root } };
  }
  return { command: 'ez-lsp', args: [], options: { cwd: workspaceRoot() } };
}
