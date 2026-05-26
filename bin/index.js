#!/usr/bin/env node

const { spawn } = require('child_process');
const path = require('path');

// Path to the python script inside the package
const pythonScriptPath = path.join(__dirname, '../biju/bijucli.py');

// Determine Python command depending on platform
function getPythonCommand() {
    return process.platform === 'win32' ? 'python' : 'python3';
}

const pythonCmd = getPythonCommand();

// Spawn the Python CLI subprocess
// 'inherit' ensures prompt_toolkit raw TTY inputs, colors, and live streaming work perfectly
const child = spawn(pythonCmd, [pythonScriptPath, ...process.argv.slice(2)], {
    stdio: 'inherit',
    shell: true
});

child.on('error', (err) => {
    console.error(`\n❌ Error: Failed to start Biju CLI.`);
    console.error(`Please ensure Python 3 is installed and available in your PATH as '${pythonCmd}'.`);
    console.error(`Detailed error: ${err.message}\n`);
    process.exit(1);
});

child.on('exit', (code) => {
    process.exit(code === null ? 0 : code);
});
