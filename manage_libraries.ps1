# Photo Heatmap Viewer - Library Management Script
param (
    [string]$command = "",
    [string]$libraryName = "",
    [string]$description = "",
    [string]$sourceDir = "",
    [string]$dbPath = "photo_library.db"
)

# Show help if no command provided
if ($command -eq "") {
    Write-Host "Photo Heatmap Library Management Tool"
    Write-Host "====================================="
    Write-Host ""
    Write-Host "Commands:"
    Write-Host "  list                   - List all libraries in the database"
    Write-Host "  create <name> <dir>    - Create a new library with the specified name and source directory"
    Write-Host "  import <name> <dir>    - Import photos from directory into an existing library"
    Write-Host "  update <name> <newdir> - Update source directory for a library"
    Write-Host "  rename <old> <new>     - Rename a library"
    Write-Host "  delete <name>          - Delete a library and all its photos"
    Write-Host "  export                 - Export all library data to JSON"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\manage_libraries.ps1 list"
    Write-Host "  .\manage_libraries.ps1 create 'Vacation 2024' 'D:\Photos\Vacation2024' -description 'Summer vacation photos'"
    Write-Host "  .\manage_libraries.ps1 import 'Vacation 2024' 'E:\More Photos\NewVacation'"
    Write-Host "  .\manage_libraries.ps1 export"
    exit 0
}

# Check if the command requires a library name
if (@("create", "import", "update", "rename", "delete") -contains $command -and $libraryName -eq "") {
    Write-Host "Error: Library name is required for this command"
    exit 1
}

# Execute commands
switch ($command.ToLower()) {
    "list" {
        Write-Host "Listing libraries..."
        python -c "import sqlite3; conn = sqlite3.connect('$dbPath'); c = conn.cursor(); c.execute('SELECT id, name, description, source_dirs FROM libraries'); print('ID  | Name                | Photos | Description'); print('-' * 60); for row in c.fetchall(): id, name, desc, dirs = row; c.execute('SELECT COUNT(*) FROM photos WHERE library_id = ?', (id,)); count = c.fetchone()[0]; print(f'{id:<4}| {name:<20} | {count:<6} | {desc}'); print('\nSource Directories:'); if dirs: import json; for dir in json.loads(dirs): print(f'  - {dir}'); conn.close()"
    }
    
    "create" {
        if ($sourceDir -eq "") {
            Write-Host "Error: Source directory is required for creating a library"
            exit 1
        }
        
        Write-Host "Creating library '$libraryName'..."
        # First create the library entry
        python -c "import sqlite3, json; conn = sqlite3.connect('$dbPath'); c = conn.cursor(); c.execute('INSERT INTO libraries (name, description, source_dirs) VALUES (?, ?, ?)', ('$libraryName', '$description', json.dumps(['$sourceDir']))); conn.commit(); print('Library created with ID:', c.lastrowid); conn.close()"
        
        # Then import photos
        Write-Host "Importing photos from '$sourceDir'..."
        python process_photos.py --process "$sourceDir" --db "$dbPath" --library "$libraryName" --description "$description"
        
        # Export updated JSON
        python process_photos.py --export --db "$dbPath"
    }
    
    "import" {
        if ($sourceDir -eq "") {
            Write-Host "Error: Source directory is required for importing photos"
            exit 1
        }
        
        Write-Host "Importing photos from '$sourceDir' into library '$libraryName'..."
        python process_photos.py --process "$sourceDir" --db "$dbPath" --library "$libraryName"
        
        # Update the library's source directories
        python -c "import sqlite3, json; conn = sqlite3.connect('$dbPath'); c = conn.cursor(); c.execute('SELECT source_dirs FROM libraries WHERE name = ?', ('$libraryName',)); row = c.fetchone(); dirs = json.loads(row[0]) if row and row[0] else []; if '$sourceDir' not in dirs: dirs.append('$sourceDir'); c.execute('UPDATE libraries SET source_dirs = ? WHERE name = ?', (json.dumps(dirs), '$libraryName')); conn.commit(); conn.close()"
        
        # Export updated JSON
        python process_photos.py --export --db "$dbPath"
    }
    
    "update" {
        if ($sourceDir -eq "") {
            Write-Host "Error: New source directory is required for updating a library"
            exit 1
        }
        
        Write-Host "Updating library '$libraryName' source directory to '$sourceDir'..."
        python -c "import sqlite3, json; conn = sqlite3.connect('$dbPath'); c = conn.cursor(); c.execute('UPDATE libraries SET source_dirs = ? WHERE name = ?', (json.dumps(['$sourceDir']), '$libraryName')); if c.rowcount > 0: print('Library updated successfully'); else: print('Library not found'); conn.commit(); conn.close()"
    }
    
    "rename" {
        if ($sourceDir -eq "") {
            Write-Host "Error: New name is required (use the sourceDir parameter for the new name)"
            exit 1
        }
        
        $newName = $sourceDir
        Write-Host "Renaming library '$libraryName' to '$newName'..."
        python -c "import sqlite3; conn = sqlite3.connect('$dbPath'); c = conn.cursor(); c.execute('UPDATE libraries SET name = ? WHERE name = ?', ('$newName', '$libraryName')); if c.rowcount > 0: print('Library renamed successfully'); else: print('Library not found'); conn.commit(); conn.close()"
    }
    
    "delete" {
        # Confirm deletion
        $confirm = Read-Host -Prompt "Are you sure you want to delete library '$libraryName' and all its photos? (y/n)"
        if ($confirm -ne "y") {
            Write-Host "Operation cancelled"
            exit 0
        }
        
        Write-Host "Deleting library '$libraryName'..."
        python -c "import sqlite3; conn = sqlite3.connect('$dbPath'); c = conn.cursor(); c.execute('SELECT id FROM libraries WHERE name = ?', ('$libraryName',)); row = c.fetchone(); if row: lib_id = row[0]; c.execute('SELECT COUNT(*) FROM photos WHERE library_id = ?', (lib_id,)); count = c.fetchone()[0]; print(f'Deleting {count} photos...'); c.execute('DELETE FROM photos WHERE library_id = ?', (lib_id,)); c.execute('DELETE FROM libraries WHERE id = ?', (lib_id,)); print(f'Deleted library and {count} photos'); else: print('Library not found'); conn.commit(); conn.close()"
        
        # Export updated JSON
        python process_photos.py --export --db "$dbPath"
    }
    
    "export" {
        Write-Host "Exporting all library data to JSON..."
        python process_photos.py --export --db "$dbPath"
    }
    
    default {
        Write-Host "Unknown command: $command"
        exit 1
    }
}

Write-Host "Done!"
