import * as vscode from 'vscode';
import * as cp from 'child_process';
import {
  LanguageClient,
  LanguageClientOptions,
  Executable,
} from 'vscode-languageclient/node';

let client: LanguageClient | undefined;

import * as fs from 'fs';
import * as path from 'path';

function findPepCandidates(): string[] {
  const home = process.env.HOME || '';
  const candidates: string[] = [];

  // Scan mise python installs for pep binary
  const miseBase = path.join(home, '.local', 'share', 'mise', 'installs', 'python');
  if (fs.existsSync(miseBase)) {
    for (const ver of fs.readdirSync(miseBase).sort().reverse()) {
      const p = path.join(miseBase, ver, 'bin', 'pep');
      if (fs.existsSync(p)) candidates.push(p);
    }
  }

  // pyenv
  const pyenvBase = path.join(home, '.pyenv', 'versions');
  if (fs.existsSync(pyenvBase)) {
    for (const ver of fs.readdirSync(pyenvBase).sort().reverse()) {
      const p = path.join(pyenvBase, ver, 'bin', 'pep');
      if (fs.existsSync(p)) candidates.push(p);
    }
  }

  // Common fixed locations
  candidates.push('/opt/homebrew/bin/pep', '/usr/local/bin/pep');

  return candidates;
}

function resolvePep(output: vscode.OutputChannel): { command: string; args: string[] } {
  for (const pep of findPepCandidates()) {
    if (fs.existsSync(pep)) {
      output.appendLine(`[peppermint] resolved pep: ${pep}`);
      return { command: pep, args: ['lsp'] };
    }
  }
  output.appendLine('[peppermint] pep not found, falling back to python3 -m peppermint lsp');
  return { command: 'python3', args: ['-m', 'peppermint', 'lsp'] };
}

export function activate(context: vscode.ExtensionContext) {
  const output = vscode.window.createOutputChannel('Peppermint Language Server');
  output.appendLine('[peppermint] activating extension...');

  const { command, args } = resolvePep(output);
  output.appendLine(`[peppermint] starting server: ${command} ${args.join(' ')}`);

  const serverOptions: Executable = {
    command,
    args,
  };

  const clientOptions: LanguageClientOptions = {
    documentSelector: [{ scheme: 'file', language: 'peppermint' }],
    synchronize: {
      fileEvents: vscode.workspace.createFileSystemWatcher('**/*.pep'),
    },
  };

  client = new LanguageClient(
    'peppermint',
    'Peppermint Language Server',
    serverOptions,
    clientOptions
  );

  client.start();
}

export function deactivate(): Thenable<void> | undefined {
  return client?.stop();
}
