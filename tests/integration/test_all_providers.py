#!/usr/bin/env python3
"""
Complete Provider Integration Test
Tests the full RAG workflow with all four providers:
1. Ollama (FREE, local)
2. HuggingFace (FREE, API-based)
3. OpenAI (Paid)
4. Gemini (Free tier with limits)

This script demonstrates a complete end-to-end workflow:
- Document ingestion
- Embedding generation
- Vector storage
- Semantic search
- LLM-based question answering
"""

import os
import sys
from pathlib import Path
from typing import Dict, List
import time

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text: str):
    """Print a formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 80}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(80)}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 80}{Colors.ENDC}\n")


def print_section(text: str):
    """Print a formatted section header"""
    print(f"\n{Colors.CYAN}{'-' * 80}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text}{Colors.ENDC}")
    print(f"{Colors.CYAN}{'-' * 80}{Colors.ENDC}")


def print_success(text: str):
    """Print success message"""
    print(f"{Colors.GREEN}SUCCESS: {text}{Colors.ENDC}")


def print_error(text: str):
    """Print error message"""
    print(f"{Colors.RED}ERROR: {text}{Colors.ENDC}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.YELLOW}WARNING: {text}{Colors.ENDC}")


def print_info(text: str):
    """Print info message"""
    print(f"{Colors.CYAN}INFO: {text}{Colors.ENDC}")


class ProviderTester:
    """Tests a single provider with the complete RAG workflow"""
    
    def __init__(self, provider_name: str):
        self.provider_name = provider_name
        self.client = None
        self.test_dir = Path("test_data_provider_test")
        self.storage_path = f"test_vectors_{provider_name}.json"
        self.results = {
            "provider": provider_name,
            "success": False,
            "ingestion_time": 0,
            "query_time": 0,
            "chunks_created": 0,
            "errors": []
        }
    
    def setup(self) -> bool:
        """Setup the provider and verify prerequisites"""
        try:
            from deeprepo import DeepRepoClient
            
            print_section(f"Setting up {self.provider_name.upper()} provider")
            
            # Check prerequisites based on provider
            if self.provider_name == "ollama":
                print_info("Checking Ollama installation...")
                # Ollama should be running on localhost:11434
                import requests
                try:
                    response = requests.get("http://localhost:11434/api/tags", timeout=5)
                    if response.status_code == 200:
                        print_success("Ollama is running")
                    else:
                        raise Exception("Ollama not responding correctly")
                except Exception as e:
                    print_error(f"Ollama not available: {e}")
                    print_warning("Make sure Ollama is running: 'ollama serve'")
                    print_warning("And models are pulled: 'ollama pull nomic-embed-text' and 'ollama pull llama3.2'")
                    return False
            
            elif self.provider_name == "huggingface":
                api_key = os.environ.get("HUGGINGFACE_API_KEY") or os.environ.get("HF_TOKEN")
                if not api_key:
                    print_error("HUGGINGFACE_API_KEY or HF_TOKEN environment variable not set")
                    print_info("Get your free API key at: https://huggingface.co/settings/tokens")
                    return False
                print_success(f"HuggingFace API key found: {api_key[:10]}...")
            
            elif self.provider_name == "openai":
                api_key = os.environ.get("OPENAI_API_KEY")
                if not api_key:
                    print_error("OPENAI_API_KEY environment variable not set")
                    print_info("Get your API key at: https://platform.openai.com/api-keys")
                    return False
                print_success(f"OpenAI API key found: {api_key[:10]}...")
            
            elif self.provider_name == "gemini":
                api_key = os.environ.get("GEMINI_API_KEY")
                if not api_key:
                    print_error("GEMINI_API_KEY environment variable not set")
                    print_info("Get your free API key at: https://makersuite.google.com/app/apikey")
                    return False
                print_success(f"Gemini API key found: {api_key[:10]}...")
            
            # Initialize client
            print_info(f"Initializing DeepRepoClient with {self.provider_name} provider...")
            self.client = DeepRepoClient(
                provider_name=self.provider_name,
                storage_path=self.storage_path
            )
            print_success(f"Client initialized successfully")
            print_info(f"Provider: {self.client.provider_name}")
            
            return True
            
        except ImportError as e:
            print_error(f"Failed to import DeepRepo: {e}")
            print_info("Make sure the package is installed: pip install -e ./deeprepo_core")
            self.results["errors"].append(str(e))
            return False
        except Exception as e:
            print_error(f"Setup failed: {e}")
            self.results["errors"].append(str(e))
            return False
    
    def create_test_data(self):
        """Create test documents"""
        print_section("Creating test documents")
        
        # Create test directory
        self.test_dir.mkdir(exist_ok=True)
        
        # Test document 1: Python code
        doc1 = self.test_dir / "ml_model.py"
        doc1_content = '''"""
Machine Learning Model Training Module

This module provides utilities for training and evaluating ML models.
"""

import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score

class MLModelTrainer:
    """A class for training machine learning models."""
    
    def __init__(self, model, random_state=42):
        """
        Initialize the trainer.
        
        Args:
            model: The ML model to train (must have fit/predict methods)
            random_state: Random seed for reproducibility
        """
        self.model = model
        self.random_state = random_state
        self.is_trained = False
    
    def train(self, X, y, test_size=0.2):
        """
        Train the model on the provided data.
        
        Args:
            X: Feature matrix
            y: Target labels
            test_size: Proportion of data to use for testing
            
        Returns:
            Dictionary with training metrics
        """
        # Split the data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=self.random_state
        )
        
        # Train the model
        self.model.fit(X_train, y_train)
        self.is_trained = True
        
        # Evaluate
        train_pred = self.model.predict(X_train)
        test_pred = self.model.predict(X_test)
        
        metrics = {
            "train_accuracy": accuracy_score(y_train, train_pred),
            "test_accuracy": accuracy_score(y_test, test_pred),
            "train_precision": precision_score(y_train, train_pred, average='weighted'),
            "test_precision": precision_score(y_test, test_pred, average='weighted'),
        }
        
        return metrics
    
    def predict(self, X):
        """Make predictions on new data."""
        if not self.is_trained:
            raise ValueError("Model must be trained before making predictions")
        return self.model.predict(X)
'''
        doc1.write_text(doc1_content)
        print_success(f"Created {doc1.name} ({len(doc1_content)} chars)")
        
        # Test document 2: Documentation
        doc2 = self.test_dir / "api_guide.md"
        doc2_content = '''# API Documentation

## Authentication

All API requests require authentication using an API key. Include your API key in the header:

```
Authorization: Bearer YOUR_API_KEY
```

## Endpoints

### GET /api/users
Retrieve a list of all users.

**Parameters:**
- `limit` (optional): Maximum number of users to return (default: 100)
- `offset` (optional): Number of users to skip (default: 0)

**Response:**
```json
{
  "users": [...],
  "total": 150,
  "limit": 100,
  "offset": 0
}
```

### POST /api/users
Create a new user.

**Request Body:**
```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "role": "user"
}
```

**Response:**
```json
{
  "id": "user_123",
  "name": "John Doe",
  "email": "john@example.com",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### Rate Limits

- Free tier: 100 requests per hour
- Pro tier: 1000 requests per hour
- Enterprise: Unlimited

## Error Handling

The API uses standard HTTP status codes:
- 200: Success
- 400: Bad Request
- 401: Unauthorized
- 404: Not Found
- 500: Internal Server Error
'''
        doc2.write_text(doc2_content)
        print_success(f"Created {doc2.name} ({len(doc2_content)} chars)")
        
        print_info(f"Test directory: {self.test_dir}")
    
    def test_ingestion(self) -> bool:
        """Test document ingestion"""
        print_section("Testing document ingestion")
        
        try:
            start_time = time.time()
            
            result = self.client.ingest(
                path=str(self.test_dir),
                chunk_size=500,
                overlap=50
            )
            
            self.results["ingestion_time"] = time.time() - start_time
            self.results["chunks_created"] = result['chunks_processed']
            
            print_success("Ingestion complete!")
            print_info(f"Files scanned: {result['files_scanned']}")
            print_info(f"Chunks created: {result['chunks_processed']}")
            print_info(f"Time taken: {self.results['ingestion_time']:.2f}s")
            
            # Check stats
            stats = self.client.get_stats()
            print_info(f"Total chunks in store: {stats['total_chunks']}")
            print_info(f"Total files in store: {stats['total_files']}")
            
            return True
            
        except Exception as e:
            print_error(f"Ingestion failed: {e}")
            self.results["errors"].append(f"Ingestion: {str(e)}")
            return False
    
    def test_queries(self) -> bool:
        """Test querying the knowledge base"""
        print_section("Testing queries")
        
        queries = [
            "How do I train a machine learning model?",
            "What are the API rate limits?",
            "How do I create a new user via the API?",
        ]
        
        all_success = True
        total_time = 0
        
        for i, question in enumerate(queries, 1):
            print(f"\n{Colors.BOLD}Query {i}:{Colors.ENDC} {question}")
            
            try:
                start_time = time.time()
                response = self.client.query(question, top_k=3)
                query_time = time.time() - start_time
                total_time += query_time
                
                print(f"\n{Colors.GREEN}Answer:{Colors.ENDC}")
                print(response['answer'][:300] + "..." if len(response['answer']) > 300 else response['answer'])
                
                print(f"\n{Colors.CYAN}Sources: {len(response['sources'])}{Colors.ENDC}")
                for source in response['sources'][:2]:  # Show first 2 sources
                    print(f"  - {source[:80]}...")
                
                print_info(f"Query time: {query_time:.2f}s")
                
            except Exception as e:
                print_error(f"Query failed: {e}")
                self.results["errors"].append(f"Query '{question}': {str(e)}")
                all_success = False
        
        self.results["query_time"] = total_time / len(queries) if queries else 0
        print_success(f"Average query time: {self.results['query_time']:.2f}s")
        
        return all_success
    
    def cleanup(self):
        """Clean up test files"""
        print_section("Cleaning up")
        
        try:
            # Remove test files
            for file in self.test_dir.glob("*"):
                file.unlink()
            self.test_dir.rmdir()
            
            # Remove vector store
            Path(self.storage_path).unlink(missing_ok=True)
            
            print_success("Cleanup complete")
        except Exception as e:
            print_warning(f"Cleanup warning: {e}")
    
    def run(self) -> Dict:
        """Run the complete test"""
        try:
            if not self.setup():
                return self.results
            
            self.create_test_data()
            
            if not self.test_ingestion():
                return self.results
            
            if not self.test_queries():
                self.results["success"] = False
                return self.results
            
            self.results["success"] = True
            print_success(f"{self.provider_name.upper()} test completed successfully!")
            
        except Exception as e:
            print_error(f"Test failed: {e}")
            self.results["errors"].append(str(e))
        finally:
            self.cleanup()
        
        return self.results


def main():
    """Main test runner"""
    print_header("DeepRepo - Complete Provider Integration Test")
    
    print(f"""
{Colors.BOLD}This script will test the complete RAG workflow with all providers:{Colors.ENDC}

{Colors.GREEN}1. Ollama{Colors.ENDC}       - FREE, unlimited, runs locally
{Colors.GREEN}2. HuggingFace{Colors.ENDC} - FREE tier with generous limits
{Colors.YELLOW}3. OpenAI{Colors.ENDC}      - Paid, most reliable
{Colors.YELLOW}4. Gemini{Colors.ENDC}      - Free tier with strict limits

{Colors.BOLD}Prerequisites:{Colors.ENDC}
- Ollama: Install and run 'ollama serve', pull models
- HuggingFace: Set HUGGINGFACE_API_KEY or HF_TOKEN
- OpenAI: Set OPENAI_API_KEY
- Gemini: Set GEMINI_API_KEY
""")
    
    # Determine which providers to test
    if len(sys.argv) > 1:
        providers = sys.argv[1:]
    else:
        print(f"{Colors.BOLD}Testing all available providers...{Colors.ENDC}")
        print(f"{Colors.CYAN}(You can specify providers as arguments, e.g., python test_all_providers.py ollama openai){Colors.ENDC}\n")
        providers = ["ollama", "huggingface", "openai", "gemini"]
    
    # Run tests
    all_results = []
    
    for provider in providers:
        print_header(f"Testing {provider.upper()} Provider")
        tester = ProviderTester(provider)
        results = tester.run()
        all_results.append(results)
        time.sleep(2)  # Small delay between providers
    
    # Print summary
    print_header("Test Summary")
    
    print(f"\n{Colors.BOLD}{'Provider':<15} {'Status':<10} {'Chunks':<10} {'Ingest Time':<15} {'Query Time':<15}{Colors.ENDC}")
    print("-" * 80)
    
    for result in all_results:
        status = f"{Colors.GREEN}PASS{Colors.ENDC}" if result['success'] else f"{Colors.RED}FAIL{Colors.ENDC}"
        provider = f"{Colors.BOLD}{result['provider']:<15}{Colors.ENDC}"
        chunks = f"{result['chunks_created']:<10}"
        ingest_time = f"{result['ingestion_time']:.2f}s" if result['ingestion_time'] > 0 else "N/A"
        query_time = f"{result['query_time']:.2f}s" if result['query_time'] > 0 else "N/A"
        
        print(f"{provider} {status:<18} {chunks} {ingest_time:<15} {query_time:<15}")
        
        if result['errors']:
            for error in result['errors']:
                print(f"  {Colors.RED}Error: {error}{Colors.ENDC}")
    
    # Overall status
    print("\n" + "=" * 80)
    success_count = sum(1 for r in all_results if r['success'])
    total_count = len(all_results)
    
    if success_count == total_count:
        print(f"{Colors.GREEN}{Colors.BOLD}ALL TESTS PASSED ({success_count}/{total_count}){Colors.ENDC}")
    elif success_count > 0:
        print(f"{Colors.YELLOW}{Colors.BOLD}PARTIAL SUCCESS ({success_count}/{total_count}){Colors.ENDC}")
    else:
        print(f"{Colors.RED}{Colors.BOLD}ALL TESTS FAILED (0/{total_count}){Colors.ENDC}")
    
    print("=" * 80)
    
    # Provider recommendations
    print(f"\n{Colors.BOLD}Recommendations:{Colors.ENDC}\n")
    
    successful_providers = [r['provider'] for r in all_results if r['success']]
    
    if 'ollama' in successful_providers:
        print(f"{Colors.GREEN}Ollama{Colors.ENDC} - Best for: FREE unlimited local usage, privacy, offline work")
    if 'huggingface' in successful_providers:
        print(f"{Colors.GREEN}HuggingFace{Colors.ENDC} - Best for: FREE cloud-based, no local installation needed")
    if 'openai' in successful_providers:
        print(f"{Colors.GREEN}OpenAI{Colors.ENDC} - Best for: Production apps, most reliable, best quality")
    if 'gemini' in successful_providers:
        print(f"{Colors.GREEN}Gemini{Colors.ENDC} - Best for: Limited free tier, Google ecosystem")
    
    print(f"\n{Colors.CYAN}For most users, we recommend starting with Ollama (100% free, unlimited){Colors.ENDC}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
