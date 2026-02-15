# Test logging system
import sys
sys.path.insert(0, r'D:\2bktest\MDview\OmniAgentAs-desk\backend')

from app.utils.logger import api_logger

print("=== Testing API Logger ===")

# Test request start
request_id = api_logger.log_request_start("zhipuai", "glm-4-flash", 100, 5)
print(f"Request ID: {request_id}")

# Test response
api_logger.log_response_with_time(request_id, "zhipuai", 200, 500)

# Another request
request_id2 = api_logger.log_request_start("opencode", "kimi-free", 50, 0)
api_logger.log_response_with_time(request_id2, "opencode", 200, 200)

# Test error
api_logger.log_error("test", "Test error")

# Test switch
api_logger.log_switch("zhipuai", "opencode", True)

print("\n=== Checking Log Files ===")
import os
log_dir = r'D:\2bktest\MDview\OmniAgentAs-desk\backend\logs'
if os.path.exists(log_dir):
    for f in os.listdir(log_dir):
        if f.endswith('.log'):
            filepath = os.path.join(log_dir, f)
            with open(filepath, 'r', encoding='utf-8') as file:
                lines = file.readlines()
                print(f"\nFile: {f}")
                print(f"Total lines: {len(lines)}")
                unique_lines = set(lines)
                if len(unique_lines) < len(lines):
                    print(f"WARNING: Duplicates found! Unique: {len(unique_lines)}")
                else:
                    print("OK: No duplicates")
                print("\nLast 5 entries:")
                for line in lines[-5:]:
                    print(f"  {line.strip()}")

print("\n=== Done ===")
