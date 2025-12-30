# Using DeepRepo to Automate Your AI Coding Workflow

This guide shows you how to use DeepRepo with Cursor, Antigravity, and other AI assistants to automate your development workflow.

---

## Table of Contents

1. [Quick Wins: Instant Use Cases](#quick-wins-instant-use-cases)
2. [Workflow 1: AI-Powered Code Understanding](#workflow-1-ai-powered-code-understanding)
3. [Workflow 2: Context Injection for AI Assistants](#workflow-2-context-injection-for-ai-assistants)
4. [Workflow 3: Automated Documentation](#workflow-3-automated-documentation)
5. [Workflow 4: Code Review Automation](#workflow-4-code-review-automation)
6. [Workflow 5: Onboarding Assistant](#workflow-5-onboarding-assistant)
7. [Advanced: Building Custom AI Tools](#advanced-building-custom-ai-tools)
8. [Integration Examples](#integration-examples)

---

## Quick Wins: Instant Use Cases

Here are things you can do **right now** with DeepRepo:

### 1. **Understand Any New Codebase in Minutes**

```python
from deeprepo import DeepRepoClient

# Index a new project you just cloned
client = DeepRepoClient(provider_name="ollama")  # FREE!
client.ingest("./new-project")

# Ask questions
response = client.query("What does this project do?")
print(response['answer'])

response = client.query("How do I run tests?")
print(response['answer'])

response = client.query("Where is the authentication logic?")
print(response['answer'])
```

### 2. **Get Instant Context for Your Current Task**

```python
# When working on a feature
response = client.query("Show me all API endpoints related to user management")
print(response['answer'])
print("\nSources:", [s['metadata']['file'] for s in response['sources']])
```

### 3. **Find Examples in Your Codebase**

```python
# Need to know how to do something?
response = client.query("Show me examples of how we handle database transactions")
print(response['answer'])
```

---

## Workflow 1: AI-Powered Code Understanding

### Problem
You're joining a new project or need to understand a complex codebase quickly.

### Solution: DeepRepo Knowledge Base

**Create a script: `understand_codebase.py`**

```python
#!/usr/bin/env python3
"""
AI-Powered Codebase Explorer
Usage: python understand_codebase.py /path/to/project
"""

import sys
from deeprepo import DeepRepoClient

def explore_codebase(project_path):
    print(f"Indexing {project_path}...")
    
    client = DeepRepoClient(provider_name="ollama")
    result = client.ingest(project_path)
    
    print(f"Indexed {result['chunks_processed']} chunks from {result['files_scanned']} files\n")
    
    # Common onboarding questions
    questions = [
        "What is the main purpose of this project?",
        "What's the tech stack used?",
        "How is the project structured?",
        "What are the main entry points?",
        "How do I run this project locally?",
        "What are the key features?",
        "Where should I start reading the code?",
    ]
    
    print("Let me explain this codebase:\n")
    print("="*70)
    
    for i, question in enumerate(questions, 1):
        print(f"\n{i}. {question}")
        response = client.query(question, top_k=3)
        print(f"\n{response['answer']}\n")
        print("-"*70)
    
    # Interactive mode
    print("\n\nInteractive Mode - Ask me anything about this codebase!")
    print("(Type 'exit' to quit)\n")
    
    while True:
        question = input("Your question: ")
        if question.lower() in ['exit', 'quit', 'q']:
            break
        
        response = client.query(question)
        print(f"\n{response['answer']}\n")
        
        if response.get('sources'):
            print("Relevant files:")
            for source in response['sources'][:3]:
                file = source['metadata']['file']
                score = source['score']
                print(f"   • {file} (relevance: {score:.2f})")
            print()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python understand_codebase.py /path/to/project")
        sys.exit(1)
    
    explore_codebase(sys.argv[1])
```

**Usage:**
```bash
python understand_codebase.py ~/projects/my-app
```

---

## Workflow 2: Context Injection for AI Assistants

### Problem
When using Cursor or Antigravity, they don't have full context about your entire codebase.

### Solution: DeepRepo Context Provider

**Create: `ai_context_provider.py`**

```python
#!/usr/bin/env python3
"""
Provides rich context to AI assistants like Cursor or Antigravity.
Saves context to a file that you can @mention in your AI chat.
"""

from deeprepo import DeepRepoClient
import json
import sys

class AIContextProvider:
    def __init__(self, project_path):
        self.client = DeepRepoClient(provider_name="ollama")
        print(f"Loading knowledge base for {project_path}...")
        self.client.ingest(project_path)
        print("Ready!\n")
    
    def get_context_for_task(self, task_description):
        """Get relevant context for a coding task."""
        
        # Query for relevant code
        response = self.client.query(
            f"What code is relevant for this task: {task_description}",
            top_k=10
        )
        
        # Build context document
        context = {
            "task": task_description,
            "answer": response['answer'],
            "relevant_files": [],
            "code_snippets": []
        }
        
        for source in response['sources']:
            file_info = {
                "file": source['metadata']['file'],
                "relevance_score": source['score'],
                "snippet": source['text'][:500]  # First 500 chars
            }
            context['relevant_files'].append(file_info)
        
        return context
    
    def save_context_file(self, task_description, output_file=".ai_context.md"):
        """Save context as a Markdown file you can @mention in Cursor/Antigravity."""
        
        context = self.get_context_for_task(task_description)
        
        markdown = f"""# AI Context: {task_description}

## Task Overview
{context['answer']}

## Relevant Files

"""
        for i, file_info in enumerate(context['relevant_files'], 1):
            markdown += f"""
### {i}. {file_info['file']} (Relevance: {file_info['relevance_score']:.2f})

```
{file_info['snippet']}
```

"""
        
        with open(output_file, 'w') as f:
            f.write(markdown)
        
        print(f"Context saved to {output_file}")
        print(f"\nIn Cursor/Antigravity, type: @{output_file}")
        print("   Then describe your task and the AI will have full context!\n")
        
        return output_file


def main():
    if len(sys.argv) < 3:
        print("Usage: python ai_context_provider.py <project_path> <task_description>")
        print("\nExample:")
        print('  python ai_context_provider.py ~/my-app "Add user authentication"')
        sys.exit(1)
    
    project_path = sys.argv[1]
    task_description = " ".join(sys.argv[2:])
    
    provider = AIContextProvider(project_path)
    provider.save_context_file(task_description)


if __name__ == "__main__":
    main()
```

**Usage with Cursor/Antigravity:**

```bash
# Get context for your current task
python ai_context_provider.py ~/my-project "Add authentication to the API"

# This creates .ai_context.md

# In Cursor or AI chat, type:
# @.ai_context.md Help me implement authentication
```

Now your AI assistant has **full context** from your codebase!

---

## Workflow 3: Automated Documentation

### Problem
Documentation is always out of date.

### Solution: Auto-Generate Docs from Code

**Create: `auto_document.py`**

```python
#!/usr/bin/env python3
"""
Automatically generate documentation from your codebase.
"""

from deeprepo import DeepRepoClient

class AutoDocumenter:
    def __init__(self, project_path):
        self.client = DeepRepoClient(provider_name="ollama")
        self.client.ingest(project_path)
    
    def generate_readme(self, output_file="AUTO_GENERATED_README.md"):
        """Generate a comprehensive README."""
        
        sections = {
            "Overview": "What is the main purpose and functionality of this project?",
            "Architecture": "How is this project architecturally structured? What are the main components?",
            "Tech Stack": "What technologies, frameworks, and libraries does this project use?",
            "Getting Started": "How do I set up and run this project locally? What are the prerequisites?",
            "Key Features": "What are the main features of this project?",
            "API Documentation": "What are the main API endpoints or interfaces?",
            "Testing": "How do I run tests? What testing frameworks are used?",
            "Contributing": "What should developers know when contributing to this project?",
        }
        
        readme = "# Project Documentation\n\n"
        readme += "*Auto-generated using DeepRepo*\n\n"
        readme += "---\n\n"
        
        for section, question in sections.items():
            print(f"Generating: {section}...")
            response = self.client.query(question, top_k=5)
            
            readme += f"## {section}\n\n"
            readme += f"{response['answer']}\n\n"
            
            # Add source references
            if response.get('sources'):
                readme += "**Source files:**\n"
                unique_files = set()
                for source in response['sources'][:5]:
                    file = source['metadata']['file']
                    if file not in unique_files:
                        readme += f"- `{file}`\n"
                        unique_files.add(file)
                readme += "\n"
            
            readme += "---\n\n"
        
        with open(output_file, 'w') as f:
            f.write(readme)
        
        print(f"\nDocumentation generated: {output_file}")
        return output_file


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python auto_document.py <project_path>")
        sys.exit(1)
    
    documenter = AutoDocumenter(sys.argv[1])
    documenter.generate_readme()
```

**Usage:**
```bash
python auto_document.py ~/my-project
# Creates AUTO_GENERATED_README.md
```

---

## Workflow 4: Code Review Automation

### Problem
Need to understand what changed in a PR and its impact.

### Solution: AI Code Review Assistant

**Create: `code_review_assistant.py`**

```python
#!/usr/bin/env python3
"""
AI-powered code review assistant.
Analyzes changes and provides context.
"""

from deeprepo import DeepRepoClient
import subprocess

class CodeReviewAssistant:
    def __init__(self, project_path):
        self.client = DeepRepoClient(provider_name="ollama")
        self.client.ingest(project_path)
        self.project_path = project_path
    
    def get_changed_files(self, branch="main"):
        """Get files changed in current branch vs main."""
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", branch],
                cwd=self.project_path,
                capture_output=True,
                text=True
            )
            return result.stdout.strip().split('\n')
        except:
            return []
    
    def review_changes(self, changed_files):
        """Generate review comments for changed files."""
        
        print("AI Code Review\n")
        print("="*70 + "\n")
        
        for file in changed_files:
            if not file:
                continue
            
            print(f"{file}\n")
            
            # Ask AI about this file
            questions = [
                f"What is the purpose of {file}?",
                f"What other parts of the codebase depend on {file}?",
                f"What should I check when reviewing changes to {file}?",
            ]
            
            for question in questions:
                response = self.client.query(question, top_k=3)
                print(f"   • {response['answer'][:200]}...")
            
            print("\n" + "-"*70 + "\n")


if __name__ == "__main__":
    import sys
    
    project_path = sys.argv[1] if len(sys.argv) > 1 else "."
    
    assistant = CodeReviewAssistant(project_path)
    changed_files = assistant.get_changed_files()
    
    if changed_files:
        assistant.review_changes(changed_files)
    else:
        print("No changes detected")
```

**Usage:**
```bash
python code_review_assistant.py ~/my-project
```

---

## Workflow 5: Onboarding Assistant

### Problem
New team members need to understand the codebase.

### Solution: Interactive Onboarding Bot

**Create: `onboarding_bot.py`**

```python
#!/usr/bin/env python3
"""
Interactive onboarding assistant for new developers.
"""

from deeprepo import DeepRepoClient

def onboarding_session(project_path):
    print("Welcome to the team!\n")
    print("I'm your AI onboarding assistant. Let me help you understand this codebase.\n")
    
    client = DeepRepoClient(provider_name="ollama")
    
    print("Indexing the codebase... (this takes a minute)\n")
    result = client.ingest(project_path)
    print(f"Indexed {result['files_scanned']} files\n")
    
    # Guided tour
    tour = [
        ("Project Overview", "Give me a high-level overview of what this project does"),
        ("Architecture", "Explain the overall architecture and main components"),
        ("Your First Task", "What would be a good first task for a new developer?"),
        ("Common Tasks", "What are the most common development tasks in this project?"),
        ("Development Setup", "How do I set up my development environment?"),
    ]
    
    print("Let me give you a guided tour:\n")
    print("="*70 + "\n")
    
    for title, question in tour:
        print(f"## {title}\n")
        response = client.query(question, top_k=5)
        print(f"{response['answer']}\n")
        
        if response.get('sources'):
            print("Key files to check:")
            for source in response['sources'][:3]:
                print(f"   • {source['metadata']['file']}")
        
        print("\n" + "-"*70 + "\n")
        input("Press Enter to continue...")
        print()
    
    # Free-form Q&A
    print("\n Now ask me anything! (Type 'exit' to quit)\n")
    
    while True:
        question = input("You: ")
        if question.lower() in ['exit', 'quit', 'done']:
            print("\nGood luck with your onboarding!")
            break
        
        response = client.query(question)
        print(f"\nAssistant: {response['answer']}\n")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python onboarding_bot.py <project_path>")
        sys.exit(1)
    
    onboarding_session(sys.argv[1])
```

---

## Advanced: Building Custom AI Tools

### 1. **VS Code Extension (Concept)**

You could build a VS Code extension that:

```python
# vscode_extension_backend.py
from deeprepo import DeepRepoClient
from flask import Flask, request, jsonify

app = Flask(__name__)
client = None

@app.route('/init', methods=['POST'])
def init_project():
    global client
    project_path = request.json['project_path']
    client = DeepRepoClient(provider_name="ollama")
    client.ingest(project_path)
    return jsonify({"status": "ready"})

@app.route('/query', methods=['POST'])
def query():
    question = request.json['question']
    response = client.query(question)
    return jsonify(response)

if __name__ == '__main__':
    app.run(port=5000)
```

### 2. **Git Hooks for Automated Reviews**

**Create: `.git/hooks/pre-commit`**

```bash
#!/bin/bash
# AI-powered pre-commit check

python << END
from deeprepo import DeepRepoClient
import subprocess

# Get staged files
result = subprocess.run(['git', 'diff', '--cached', '--name-only'], 
                       capture_output=True, text=True)
files = result.stdout.strip().split('\n')

client = DeepRepoClient(provider_name="ollama")
client.ingest(".")

for file in files:
    if file.endswith('.py'):
        response = client.query(f"What should I check before committing changes to {file}?")
        print(f"\nReview checklist for {file}:")
        print(response['answer'])

END
```

### 3. **Slack Bot for Code Questions**

```python
# slack_bot.py
from slack_bolt import App
from deeprepo import DeepRepoClient

app = App(token="your-slack-token")
client = DeepRepoClient(provider_name="ollama")
client.ingest("./your-project")

@app.message("ask-code")
def handle_code_question(message, say):
    question = message['text'].replace('ask-code', '').strip()
    response = client.query(question)
    
    say(f"{response['answer']}\n\n" + 
        f"Relevant files: {', '.join([s['metadata']['file'] for s in response['sources'][:3]])}")

if __name__ == "__main__":
    app.start(port=3000)
```

---

## Integration Examples

### **With Cursor**

1. **Create context file before coding:**
```bash
python ai_context_provider.py ~/my-project "Add OAuth authentication"
```

2. **In Cursor, start chat:**
```
@.ai_context.md I need to add OAuth authentication. 
Show me where to start and what files to modify.
```

Cursor now has full context from DeepRepo!

### **With Antigravity (or any AI assistant)**

1. **Run DeepRepo query:**
```python
from deeprepo import DeepRepoClient

client = DeepRepoClient(provider_name="ollama")
client.ingest("./my-project")

response = client.query("Explain the authentication flow")
print(response['answer'])
```

2. **Copy the answer + sources to your AI chat:**
```
I'm working on a project with this authentication flow:
[paste DeepRepo answer]

Based on this, help me add 2FA support.
```

### **As a CLI Tool**

```bash
# Add to ~/.bashrc or ~/.zshrc
alias ask-code='python -c "from deeprepo import DeepRepoClient; c = DeepRepoClient(provider_name=\"ollama\"); c.ingest(\".\"); print(c.query(input(\"Question: \"))[\"answer\"])"'

# Then use:
cd ~/my-project
ask-code
# Question: How do I run tests?
```

---

## Recommended Daily Workflow

### Morning Standup
```bash
# Get context for today's work
python ai_context_provider.py ~/my-project "Implement user profile page"
```

### During Development
```bash
# Quick questions
python -c "
from deeprepo import DeepRepoClient
c = DeepRepoClient(provider_name='ollama')
c.ingest('.')
print(c.query('How do we handle errors in API calls?')['answer'])
"
```

### Before Commit
```bash
# Review your changes
python code_review_assistant.py .
```

### End of Day
```bash
# Update documentation
python auto_document.py ~/my-project
```

---

## Pro Tips

1. **Cache Your Index**: Keep a long-running DeepRepo instance to avoid re-ingesting:
   ```python
   # Keep this running in a terminal
   python -c "
   from deeprepo import DeepRepoClient
   import code
   client = DeepRepoClient(provider_name='ollama')
   client.ingest('.')
   code.interact(local={'client': client})
   "
   ```

2. **Project-Specific Scripts**: Create a `scripts/` folder with project-specific DeepRepo tools

3. **Share with Team**: Commit DeepRepo scripts to your repo so the whole team can use them

4. **Combine with Git**: Use DeepRepo to understand what changed:
   ```bash
   git diff main...feature-branch --name-only | xargs python ask_about_files.py
   ```

---

## Next Steps

1. **Choose 1-2 workflows** from above that fit your needs
2. **Create the scripts** in your project
3. **Integrate with your daily routine**
4. **Share with your team**
5. **Build custom tools** for your specific needs

---

**Your DeepRepo + AI workflow is now supercharged!** 

Questions? Build something cool with DeepRepo? Share it!
