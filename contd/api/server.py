from fastapi import FastAPI
from concurrent import futures
import grpc
import threading
import uvicorn
import logging
import time

from contd.api.routes import router as workflow_router
from contd.api.proto import workflow_pb2_grpc
from contd.api.grpc_service import WorkflowService
from contd.core.engine import ExecutionEngine

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("contd.server")

app = FastAPI(title="Contd.ai API", version="0.1.0")

# Include routes
app.include_router(workflow_router)
from contd.api.auth_routes import router as auth_router
app.include_router(auth_router)

# gRPC Server
grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
workflow_pb2_grpc.add_WorkflowServiceServicer_to_server(WorkflowService(), grpc_server)
grpc_server.add_insecure_port('[::]:50051')

@app.on_event("startup")
async def startup_event():
    logger.info("Starting gRPC server on port 50051")
    grpc_server.start()
    
    # Initialize engine
    ExecutionEngine.get_instance()
    logger.info("Engine initialized")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Stopping gRPC server")
    grpc_server.stop(0)

def main():
    """Entry point to run the server"""
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
