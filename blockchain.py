import os
import sys
from flask import Flask, jsonify, request
from flask_executor import Executor
import logging
from datetime import datetime
import random
from merkletools import MerkleTools
import pickle
import hashlib
import json
import requests
import atexit

"""
# Opdracht:	    Code en verantwoording, Blockchain
"""

# set the logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# the flask instance
app = Flask(__name__)
executor = Executor(app)


class Blockchain():
    def __init__(self):
        self.chain = []
        self.nodes = []
        self.synced = False
        return

    def get_chain(self, sync=False):
        """
        Gets the complete chain from one of the other nodes
        If no persist local chain take over the given chain after validation.
        If there is a persisted chain, slice a piece of the supplied chain and
        validate it
        """
        node = self.get_random_node()
        if node == sportbond_uid:
            return
        node_url = f"http://localhost:{node}/chain"
        response = requests.get(node_url)
        if response.status_code != 200:
            logging.critical(f"Could not get the chain from node: {node}")

        given_chain = response.json()
        if sync is True:
            local_chain_len = len(self.chain)
            given_chain_len = len(given_chain)
            if local_chain_len == given_chain_len:
                logging.info("Our chain was still in sync with the network")
                return
            given_chain = self.chain + given_chain[local_chain_len:]
            diff_in_blocks = given_chain_len - local_chain_len
            logging.warning(f"We are {diff_in_blocks} block(s) behind")

        if not self.validate_chain(given_chain):
            logging.critical(f"Received an invalid chain from node: {node}")
        else:
            self.chain = given_chain
            logging.info(f"Got a valid chain from node: {node}")
        self.synced = True
        return

    def get_index(self):
        """
        :return: The len of the chainlist
        """
        return len(self.chain)

    def get_last_hash(self):
        """
        :return: Genesis block when chain is empty or hash of last block
        """
        if len(self.chain) == 0:
            return "genesis"
        # hash the last block and return its hash
        return self.hash(self.chain[-1])

    def validate_chain(self, given_chain=None):
        """
        Validates the given chain
        :param chain: The blockchain
        :return: bool on chain status, true or false
        """
        if not self.chain:
            return True

        if len(self.chain) == len(given_chain):
            return True

        if given_chain and len(self.chain) > len(given_chain):
            return False

        # validate the given chain
        prev_block = given_chain[0]
        if prev_block["index"] != 0:
            logging.error("Genesis block not found! Chain invalid")
            return False
        for block in given_chain[1:]:
            prev_block_hash = self.hash(prev_block)
            # test if cur block has the hash of the prev block
            if block["prevhash"] != prev_block_hash:
                logging.error(
                    "Chain invalid since previous hash does not match!")
                return False
            prev_block = block
        logging.info("Chain is correct!")
        return True

    def persist_chain(self):
        """
        Make the blockchain persistant
        """
        blockchain.nodes = []
        storage.pickle_dump("blockchain", self)
        return

    def get_random_node(self, exclude=None):
        """
        Returns a random node from the nodes list, used for approval and fetching/resolving chains
        :param exclude: Optional parameter to exclude a single node (a node cannot be an approver twice).
        :return: The UID of the approver
        """
        if len(self.nodes) == 1:
            return self.nodes[0]
        if exclude and len(self.nodes) == 2 and exclude in self.nodes and exclude != sportbond_uid:
            # Node approved previous block, but is the only node alive in the chain to approve
            return exclude
        own_node = sportbond_uid
        nodelist = self.nodes[:]
        if own_node in nodelist:
            nodelist.remove(own_node)
        if exclude and exclude in nodelist:
            nodelist.remove(exclude)
        approver = random.choice(nodelist)
        logging.info(f"Found a random node: {approver}")
        return approver

    def add_block(self, block):
        """
        Add the block to our blockchain, when it is valid
        """
        self.chain.append(block)
        # persist new block
        index = self.chain[-1]["index"]
        logging.info(f"New block added with index: {index}")
        return

    @staticmethod
    def hash(data):
        """
        :param data: Data to hash
        :return: A hash of given data
        """
        string_to_hash = json.dumps(data, sort_keys=True).encode()
        return hashlib.sha256(string_to_hash).hexdigest()

    @staticmethod
    def publish_block(data):
        """
        Loops trough all the nodes to publish the block, skipps own node
        :param data: The block data
        """
        for node in blockchain.nodes:
            if node == sportbond_uid:
                continue  # do not post on our own endpoint
            node_url = f"http://localhost:{node}/block/validated"
            requests.post(node_url, json=data)
        return


class Block(object):
    def __init__(self):
        self.index = blockchain.get_index()
        self.timestamp = datetime.now().strftime("%d-%m-%Y_%H:%M:%S")
        self.creator = sportbond_uid
        self.approver = None
        self.prevhash = blockchain.get_last_hash()
        self.merkle_root = None
        self.event = {}  # the body of the block
        return

    def ship_to_approver(self):
        """
        Send the block to the given approver who then
        can distribute it to all the nodes
        :return: True on success False on failure
        """
        block_post_data = vars(self)
        if self.approver == sportbond_uid and len(blockchain.nodes) == 1:
            # add your own block since you are alone in the network
            blockchain.add_block(block_post_data)
            return True
        approver_url = f"http://localhost:{self.approver}/block/approve"
        response = requests.post(approver_url, json=block_post_data)
        if response.status_code != 200:
            return False
        return True

    @staticmethod
    def validate(block_to_approve):
        """
        Validate the current block
        :param block_to_approve: The block that should be validated
        """
        if block_to_approve["approver"] != sportbond_uid or block_to_approve["creator"] not in blockchain.nodes:
            msg = "Block invalid! Nodes unknown or invalid"
            logging.info(msg)
            return {"msg": msg, "status_code": 401}
        # we should validate this block before publishing it to the chain
        given_event = block_to_approve["event"]
        given_event_date = given_event["date"]

        # make a new merkle root and test if the event matches:
        calculated_merkle_root = Event.create_merkle_tree(
            given_event["data"]["matches"], given_event_date)
        if calculated_merkle_root != block_to_approve["merkle_root"]:
            msg = "Supplied block has tampered event data!"
            logging.error(msg)
            return {"msg": msg, "status_code": 422}

        # test if our previous hash matches given previous hash in this block
        if block_to_approve["prevhash"] != blockchain.get_last_hash():
            msg = "Supplied block previous hash does not match ours"
            logging.error(msg)
            return {"msg": msg, "status_code": 422}
        return None


class Event(object):
    def __init__(self, data):
        self.data = data
        self.valid = self.validate()
        self.merkle_tree = None
        self.date = self.data["date"]

    def validate(self):
        """
        Validates if the given event data, that should end up in a block, is valid
        it does this by validating if the list of fight matches exsists
        and that it contains atleast 2 matches!
        """
        matchlist = self.data.get("matches")
        if not matchlist or len(matchlist) <= 1:
            logging.error("Invalid event data given")
            return None
        else:
            logging.info("Valid event given")
            return True

    @staticmethod
    def create_merkle_tree(matches, date):
        """
        Here the merkle tree is created based on the given list with matches.
        The package MerkleTools is being used to generate the Merkle Tree

        The matches will first be "flattened" into a string and receive the date to make
        these unique, so no the same hash will be generated, in for example: a rematch fight
        """
        # get date and format the data
        merkle_datalist = []
        for match in matches:
            merkle_datalist.append(f"{date}{str(match)}")
        # make the tree
        try:
            mt = MerkleTools()
            mt.add_leaf(merkle_datalist, True)
            mt.make_tree()
            return mt.get_merkle_root()
        except Exception:
            return None

    def __del__(self):
        return


class Storage():
    def __init__(self, sportbond_uid):
        self.root_dir = os.getcwd()
        self.sportbond_uid = sportbond_uid
        self.persis_dir = os.path.join(
            self.root_dir, "persistance", self.sportbond_uid)
        self.cache_dir = os.path.join(self.persis_dir, "cache")
    pass

    def pickle_dump(self, name, object, cache=False):
        """
        dumps the data into a pickle
        :param name: the savename
        :param object: the object to save
        :param cache: if file should be stored in cache or persists
        """
        if not os.path.exists(self.persis_dir):
            logging.info("Persistance dirs created!")
            os.makedirs(self.persis_dir)
            os.makedirs(self.cache_dir)
        elif not os.path.exists(self.cache_dir) and cache:
            os.makedirs(self.cache_dir)

        # if cache is True we write it out to the cache dir
        dir_to_use = self.persis_dir if not cache else self.cache_dir

        file_on_disk = os.path.join(dir_to_use, f"{name}.pickle")
        with open(f"{file_on_disk}", "wb") as pfile:
            pickle.dump(object, pfile, pickle.HIGHEST_PROTOCOL)
        logging.info(f"File: {name} persisted on disk!")
        return

    def pickle_load(self, name, cache=False):
        """
        loads the pickled data
        :param name: the name of the picklefile to load
        :param cache: bool if it should come from the cached files
        :return: the object when found else a None
        """
        load_folder = self.cache_dir if cache else self.persis_dir
        data_to_load = os.path.join(load_folder, f"{name}.pickle")
        if not os.path.exists(f"{data_to_load}"):
            logging.error(f"Persistant file: {name} does not exsist")
            return None
        with open(f'{data_to_load}', 'rb') as f:
            logging.info(f"Persistant file: {name} loaded from disk")
            return pickle.load(f)
        return

    def pickle_clear(self, cache=True):
        """
        Clears the persistant data
        :param cache: bool which results in which folder to clear
        """
        logging.info("Request to remove a pickle file")

        if cache:
            dir_to_clear = os.path.join(self.cache_dir, "new_event.pickle")
        else:
            dir_to_clear = os.path.join(self.persis_dir, "blockchain.pickle")

        try:
            os.remove(dir_to_clear)
            logging.warning(f"Removed file: {dir_to_clear}")
        except Exception:
            logging.warning("Nothing to clear")
            pass
        return


@app.route("/")
def index():
    """ returns the index"""
    return "<h1>Hello Novi</h1>"


def node_manager_interaction(sportbond_uid, method):
    """
    (un)register this node to the nodemanager
    :param sportbond_uid: the unique identifier of this node
    """
    nodemanager_url = f"http://localhost:9001/{method}"
    response = requests.post(nodemanager_url, json={"name": sportbond_uid})
    if response.status_code != 200:
        logging.error(f"Could not {method}")
    else:
        logging.info(f"Node {method}ed")
    if method == "unregister":
        blockchain.nodes = []
        blockchain.synced = False
        blockchain.persist_chain()
    return


@app.route("/chain")
def chain_view():
    """
    Show the blockchain
    :return: Show the blockchain in a response with a 200 http code
    """
    return jsonify(blockchain.chain)


@app.route("/nodes", methods=["POST"])
def set_nodelist():
    """
    Sets the nodelist supplied by the node manager
    """
    alive_nodes = request.get_json()
    logging.info("The nodelist is updated")
    blockchain.nodes = alive_nodes["nodes_list"]
    if not blockchain.chain and len(blockchain.nodes) > 1 and blockchain.synced is False:
        logging.info("We need a valid chain from soneone in the network")
        blockchain.get_chain()
    if blockchain.chain:
        if blockchain.synced is False:
            blockchain.get_chain(sync=True)
    return "data received", 200


@app.route("/event/new", methods=["POST"])
def event_endpoint():
    """
    Adds a new event to the cache of this node
    :return: A HTTP response and some infor regarding the response
    """
    event_details = request.get_json()
    eventobj = Event(event_details)
    if not eventobj.valid:
        del eventobj
        return "invalid event data!", 422
    # lets create the merkle tree since the data is valid
    try:
        merkleroot = eventobj.create_merkle_tree(
            eventobj.data["matches"], eventobj.date)
        eventobj.merkle_tree = merkleroot
        # dump the created event to the cache for temp persistance
        storage.pickle_dump("new_event", eventobj, True)
    except Exception as error:
        logging.error(f"Could not build the MerkleTree: {error}")
        return "could not create the Merkle Tree", 500
    return f"Data received, merkle root created: {eventobj.merkle_tree}", 200


@app.route("/block/create")
def block_endpoint():
    """
    Creats a block from the event data, finds and approver and ships it to the approver
    :return: Returns a response message after providing the block to an approver
    """
    logging.info("Request received to create a block")
    new_block = Block()
    try:
        event_data = vars(storage.pickle_load("new_event", True))
    except Exception:
        return "Event data not found!", 404
    new_block.merkle_root = event_data["merkle_tree"]
    new_block.event = event_data
    # test if approver is not previous approver
    prev_approver = blockchain.chain[-1]["approver"] if blockchain.chain else None
    new_block.approver = blockchain.get_random_node(prev_approver)
    approver_response = new_block.ship_to_approver()
    # remove the cached event from our persistance storage
    storage.pickle_clear()
    if not approver_response:
        logging.error(
            f"Our approver: {new_block.approver} rejected the block!")
        return "Invalid block!", 422
    return f"Block creation completed and succesfull distributed to approver", 200


@app.route("/block/approve", methods=["POST"])
def approve_block():
    # / TODO ADD THIS INTO A METHOD SO WE CAN REUSE IT
    logging.info("You are selected to approve a new suggested block!")
    block_to_approve = request.get_json()
    # test if we are allowed to add this block
    invalid = Block.validate(block_to_approve)
    if invalid:
        return invalid["msg"], invalid["status_code"]
    # the given block meets all the requirements to be published!
    data = {"name": sportbond_uid, "block": block_to_approve}
    # add to our own chain
    blockchain.add_block(data["block"])
    executor.submit(blockchain.publish_block, data)
    logging.info("Block approved and distributed")
    return "done", 200


@app.route("/block/validated", methods=["POST"])
def add_block():
    received_block_data = request.get_json()
    # test if given block supplier and approver match!
    if received_block_data["name"] != received_block_data["block"]["approver"]:
        logging.error(
            "Block not added, approver not the same as the block distributor")
        return "Block not added!", 401

    # block matches all the requirements so far, lets test the hash (again)
    if received_block_data["block"]["prevhash"] != blockchain.get_last_hash():
        msg = "Supplied block previous hash does not match ours"
        logging.error(msg)
        return msg, 422
    # block matches lets add it to our chain
    blockchain.add_block(received_block_data["block"])
    return "Block added", 200


sportbond_uid = sys.argv[-1]
storage = Storage(sportbond_uid)
# test if the blockchain already exsists
blockchain = storage.pickle_load("blockchain")
if blockchain:
    node_manager_interaction(sportbond_uid, "register")
else:
    logging.info("No persisted blockchain found")
    blockchain = Blockchain()
    node_manager_interaction(sportbond_uid, "register")

atexit.register(node_manager_interaction, sportbond_uid, "unregister")

if __name__ == "__main__":
    logging.critical("Use the Makefile to spin up a node instances")
    raise SystemExit()
