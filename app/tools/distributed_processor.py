import pandas as pd
import concurrent.futures
import time
import os
from typing import List, Dict, Any, Callable

class ParallelStreamProcessor:
    """
    Simulates / Implements distributed data processing by chunking large datasets
    and processing them across multiple workers for high throughput and scalability.
    """
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers

    def process_csv_in_parallel(
        self, 
        file_path: str, 
        chunk_size: int = 1000, 
        processing_func: Callable[[pd.DataFrame], Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Processes a CSV file in parallel chunks.
        """
        if not os.path.exists(file_path):
            return [{"error": f"File {file_path} not found"}]

        print(f"Initializing Distributed Processing Engine... (Workers: {self.max_workers})")
        start_time = time.time()
        
        results = []
        
        # Read chunks
        chunks = pd.read_csv(file_path, chunksize=chunk_size)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Map processing function to chunks
            future_to_chunk = {
                executor.submit(self._worker_task, chunk, i, processing_func): i 
                for i, chunk in enumerate(chunks)
            }
            
            for future in concurrent.futures.as_completed(future_to_chunk):
                chunk_index = future_to_chunk[future]
                try:
                    data = future.result()
                    results.append(data)
                except Exception as exc:
                    print(f"Worker {chunk_index} generated an exception: {exc}")
        
        end_time = time.time()
        print(f"Distributed processing complete in {end_time - start_time:.4f}s")
        return results

    def _worker_task(self, chunk: pd.DataFrame, index: int, func: Callable) -> Dict[str, Any]:
        """The actual task run by the worker"""
        print(f"  [Worker-{index}] Processing chunk of size {len(chunk)}...")
        
        # Simulate 'distributed overhead/latency' for demonstration purposes if needed
        # time.sleep(0.1) 
        
        if func:
            return func(chunk)
        
        # Default: just return basic stats
        return {
            "chunk_index": index,
            "row_count": len(chunk),
            "total_amount": chunk.get("amount", pd.Series([0])).sum()
        }

if __name__ == "__main__":
    # Test logic
    processor = ParallelStreamProcessor(max_workers=4)
    # Use a dummy path or existing one for testing
    dummy_path = "test_upload.csv"
    if os.path.exists(dummy_path):
        results = processor.process_csv_in_parallel(dummy_path, chunk_size=5)
        print(f"Aggregated Results: {results}")
