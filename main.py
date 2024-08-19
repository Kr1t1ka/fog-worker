import json
import logging
import os
import traceback

import docker
import psutil
from fastapi import FastAPI
from starlette.responses import JSONResponse, Response

client = docker.from_env()

app = FastAPI(docs_url="/api/swagger/", openapi_url="/api/openapi.json")

WORKER_NAME = os.getenv('WORKER_NAME', 'worker_*')

logger = logging.getLogger(WORKER_NAME)

@app.get("/server/load", status_code=200)
async def get_load():
    """
    Returns the CPU load, total FLOPS, available FLOPS, percentage of available FLOPS, and available RAM.

    ---
    tags:
      - Server
    responses:
      200:
        description: Server load and available RAM information.
        content:
          application/json:
            schema:
              type: object
              properties:
                CPU_Load:
                  type: number
                  description: The CPU load as a percentage.
                Total_FLOPS:
                  type: number
                  description: The total FLOPS of the CPU.
                Available_FLOPS:
                  type: number
                  description: The available FLOPS of the CPU.
                Available_FLOPS_Percentage:
                  type: number
                  description: The percentage of available FLOPS.
                Available_RAM:
                  type: number
                  description: The available RAM in GB.
    """
    try:
        # Get CPU load
        cpu_load = psutil.cpu_percent(interval=1)

        # Get CPU information
        cpu_info = psutil.cpu_freq()
        max_freq = cpu_info.max if cpu_info.max > 0 else cpu_info.current
        current_freq = cpu_info.current
        num_cores = psutil.cpu_count(logical=False)

        # Calculate total FLOPS
        total_flops = 2 * num_cores * max_freq * 10 ** 9  # 2 FLOPs per cycle
        # Calculate available FLOPS (assuming 50% CPU utilization)
        available_flops = total_flops * (1 - cpu_load / 100)

        # Calculate percentage of available FLOPS
        available_flops_percentage = (available_flops / total_flops) * 100

        # Get available RAM
        available_ram = psutil.virtual_memory().available / 2 ** 30  # Convert to GB
        res = {
            "cpu_load": cpu_load,
            "total_FLOPS": total_flops,
            "available_FLOPS": available_flops,
            "available_FLOPS_percentage": available_flops_percentage,
            "available_RAM": available_ram,
            "current_freq": current_freq,
        }
        print(f"loder {res}")
        return res
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}, 500


@app.post("/docker/run", status_code=201)
async def run_docker_container(image: str, environment: dict = None,
                               waited: bool = False):
    """
    Runs a Docker container and returns the response.

    Args:
        image: Docker image name to run.
        environment: Environment variables to pass to the container.
        waited: Wait for the container to finish running.

    Returns:
        JSON response containing the container details.
        container_id: The container ID.
        image: The image tag.
        status: The status of the container.
        logs: The logs of the container.
    """
    print(f'worker start {image} job')
    container = client.containers.run(image, detach=True,
                                      environment=environment)
    if waited:
        container.wait()
        logs = container.logs()
        logs_dict = json.loads(logs.decode())
    else:
        logs_dict = {}
    print(f'worker finish {image} job')
    return JSONResponse(
        {
            "container_id": container.id,
            "image": container.image.tags[0],
            "status": container.status,
            "logs": logs_dict,
        }
    )


@app.delete("/docker/containers/all", status_code=204)
async def stop_all_docker_containers():
    """
    Stops all running Docker containers.
    """
    for container in client.containers.list(all=True):
        container.stop()
        container.remove()
    print('all docker containers remove')
    return Response(status_code=204)
