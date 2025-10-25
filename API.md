# API Documentation

## Backend Endpoints

### Chat and Code Generation

#### POST /api/chat
Generate chat responses and code.

**Request:**
```json
{
    "message": "string",
    "force_new": "boolean"
}
```

**Response:**
```json
{
    "result": "string",
    "code": "string"
}
```

### Code Management

#### POST /api/save_code
Save generated code to file.

**Request:**
```json
{
    "code": "string",
    "filename": "string"
}
```

**Response:**
```json
{
    "success": "boolean",
    "file_path": "string"
}
```

#### POST /api/clear_prompt_cache
Clear cached response for a prompt.

**Request:**
```json
{
    "prompt": "string"
}
```

### System Status

#### GET /api/status
Get AI models status.

**Response:**
```json
{
    "ia_chat_online": "boolean",
    "ia_code_online": "boolean",
    "status": "boolean"
}
```

### User Settings

#### GET /api/settings
Get user settings.

**Response:**
```json
{
    "theme": "string",
    "ui_preferences": {
        "sidebar_collapsed": "boolean"
    }
}
```

#### POST /api/settings
Update user settings.

**Request:**
```json
{
    "theme": "string",
    "ui_preferences": {
        "sidebar_collapsed": "boolean"
    }
}
```

## Components

### Frontend Components

#### Chat Interface
- Message bubbles for user and AI
- Code preview with syntax highlighting
- File history panel

#### Code Preview
- Syntax highlighted code display
- Save/Reject/Clear actions
- File management

#### Settings Panel
- Theme toggle
- UI preferences
- Workspace configuration

### Backend Components

#### IAAgentHybrid
Main AI agent that handles:
- Chat responses
- Code generation
- Template management
- Cache control

#### ChatHistory
Manages:
- Chat message history
- Action logging
- Code history

#### UserSettings
Handles:
- User preferences
- Theme settings
- Workspace configuration

## Data Structures

### Chat Message
```json
{
    "timestamp": "ISO datetime",
    "role": "user|ia",
    "content": "string",
    "code": "string|null"
}
```

### Action Log
```json
{
    "timestamp": "ISO datetime",
    "type": "save|reject|clear",
    "details": {
        "filename": "string",
        "code_type": "string"
    }
}
```

### User Profile
```json
{
    "theme": "light|dark",
    "recent_files": ["string"],
    "favorite_templates": ["string"],
    "ui_preferences": {
        "sidebar_collapsed": "boolean"
    }
}
```