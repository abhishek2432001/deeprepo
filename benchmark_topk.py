"""Benchmark: argpartition vs heapq for top-k selection."""

import numpy as np
import heapq
import time

def benchmark_argpartition(similarities, k):
    """NumPy argpartition approach."""
    top_k_indices = np.argpartition(similarities, -k)[-k:]
    top_k_indices = top_k_indices[np.argsort(similarities[top_k_indices])[::-1]]
    return top_k_indices

def benchmark_heapq(similarities, k):
    """Python heapq approach."""
    # heapq.nlargest returns values, we need indices
    indexed_similarities = list(enumerate(similarities))
    top_k = heapq.nlargest(k, indexed_similarities, key=lambda x: x[1])
    return np.array([idx for idx, _ in top_k])

def benchmark_full_sort(similarities, k):
    """Full sort approach."""
    sorted_indices = np.argsort(similarities)[::-1]
    return sorted_indices[:k]

def run_benchmark(n_items, k, iterations=1000):
    """Run benchmark for different methods."""
    print(f"\n{'='*60}")
    print(f"Dataset: {n_items:,} items | Top-k: {k} | Iterations: {iterations}")
    print(f"{'='*60}")
    
    # Generate random similarities
    np.random.seed(42)
    similarities = np.random.rand(n_items).astype(np.float32)
    
    methods = [
        ("argpartition (NumPy)", benchmark_argpartition),
        ("heapq (Python)", benchmark_heapq),
        ("full sort", benchmark_full_sort),
    ]
    
    results = []
    for name, func in methods:
        start = time.perf_counter()
        for _ in range(iterations):
            result = func(similarities, k)
        end = time.perf_counter()
        
        avg_time_ms = (end - start) / iterations * 1000
        results.append((name, avg_time_ms))
        print(f"{name:25} | {avg_time_ms:8.4f} ms")
    
    # Calculate speedup
    baseline = results[0][1]  # argpartition
    print(f"\n{'Speedup vs argpartition:'}")
    for name, time_ms in results:
        speedup = time_ms / baseline
        print(f"{name:25} | {speedup:6.2f}x {'(baseline)' if speedup == 1.0 else ''}")

if __name__ == "__main__":
    print("\n🚀 Top-K Selection Benchmark\n")
    
    # Test different scenarios
    run_benchmark(n_items=1_000, k=5, iterations=1000)
    run_benchmark(n_items=10_000, k=5, iterations=1000)
    run_benchmark(n_items=100_000, k=10, iterations=100)
    
    print(f"\n{'='*60}")
    print("✅ Benchmark complete!")
    print(f"{'='*60}\n")
