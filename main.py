import json
import logging
import os
import random
import traceback

import docker
import psutil
import pyopencl as cl
from fastapi import FastAPI
from starlette.responses import JSONResponse, Response

client = docker.from_env()

app = FastAPI(docs_url="/api/swagger/", openapi_url="/api/openapi.json")

WORKER_NAME = os.getenv('WORKER_NAME', 'worker_*')

logger = logging.getLogger(WORKER_NAME)


def get_gpu_info():
    # Эмуляция значений для нагрузки GPU в процентах
    gpu_load = random.uniform(0, 100)  # Значение от 0 до 100%

    # Эмуляция общей производительности в TFLOPS (например, для средней видеокарты)
    total_flops = random.uniform(5, 20)  # Значение от 5 до 20 TFLOPS

    # Эмуляция доступных FLOPS на основе нагрузки
    available_flops = total_flops * (1 - gpu_load / 100)

    # Расчет процента доступных FLOPS
    available_flops_percentage = (available_flops / total_flops) * 100

    # Формирование словаря с результатами
    return {
        "gpu_load": round(gpu_load, 2),
        "total_FLOPS": round(total_flops, 2),
        "available_FLOPS": round(available_flops, 2),
        "available_FLOPS_percentage": round(available_flops_percentage, 2),
    }


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
            "total_FLOPS": total_flops / 10**12,
            "available_FLOPS": available_flops/ 10**12,
            "available_FLOPS_percentage": available_flops_percentage,
            "available_gpu_FLOPS_percentage": random.uniform(0, 1) * 100,
            "available_RAM": available_ram,
            "current_freq": current_freq,
            "gpu": get_gpu_info()
        }
        print(f"{WORKER_NAME}: loder {res}")
        return res
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}, 500


@app.put("/server/load", status_code=200)
async def set_load(percent: int, timestamp: int):
    """
    Set load on server.
    """
    print(f'{WORKER_NAME}: set load percent:{percent} timestamp:{timestamp}')
    container = client.containers.run(
        'kr1t1ka/optimus',
        detach=True,
        environment={
            "LOAD_PERCENT": percent,
            "TIMESTAMP": timestamp
        }
    )
    return container.id


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
    print(f'{WORKER_NAME}: start {image} job')
    container = client.containers.run(image, detach=True,
                                      environment=environment)
    if waited:
        container.wait()
        logs = container.logs()
        logs_dict = json.loads(logs.decode())
    else:
        logs_dict = {}
    print(f'{WORKER_NAME}: finish {image} job')
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
    print(f'{WORKER_NAME}: all docker containers remove')
    return Response(status_code=204)
