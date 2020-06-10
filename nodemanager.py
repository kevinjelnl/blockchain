import logging
import requests
from flask import Flask, jsonify, request
from flask_executor import Executor
import json

"""
# Opdracht:	    Code en verantwoording, Blockchain
"""

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

app = Flask(__name__)
executor = Executor(app)

# for now we have the nodes in memory
alive_nodes = []
valid_nodes = ["8081", "8082", "8083", "8084"]


# def pick_node():
#     """
#     Select a random node from our alive nodes
#     :return: the nodename
#     """
#     if not alive_nodes:
#         return None
# return random.choice(alive_nodes)


def update_nodes():
    logging.info("Updating all the nodes")
    for node in alive_nodes:
        logging.info(f"Updating node: {node}")
        requests.post(
            f"http://localhost:{node}/nodes", json={"nodes_list": alive_nodes})
    return


@app.route("/nodes")
def show_nodes():
    return json.dumps(alive_nodes)


@app.route("/register", methods=["POST"])
def register_node():
    """
    Register to our private blockchain network
    Starts the function to update the nodes
    """
    new_node = request.get_json()
    if "name" not in new_node:
        return "invalid registering data", 422
    node_name = new_node["name"]
    if node_name not in valid_nodes:
        return "Register first! This is a private blockchain network", 401
    if not node_name in alive_nodes:
        alive_nodes.append(node_name)
        logging.info(f"New node in the network: {node_name}")
    executor.submit(update_nodes)
    return "Welcome aboard", 200


@app.route("/unregister", methods=["POST"])
def unregister_node():
    """
    Remove the node from our nodelist
    Starts the function to update the nodes
    """
    leaving_node = request.get_json()
    try:
        node_name = leaving_node["name"]
        alive_nodes.remove(node_name)
        logging.warn(f"Node left the network: {node_name}")
        executor.submit(update_nodes)
    except Exception as errormsg:
        logging.error(
            f"Problem removing the node: {leaving_node}, error: {errormsg}")
    finally:
        return "Goodbye", 200


@app.route("/")
def index():
    return "<h1>Hello Novi</h1>"
