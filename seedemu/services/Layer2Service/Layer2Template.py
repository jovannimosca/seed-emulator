from __future__ import annotations
from typing import Dict, List
from enum import Enum

WEB_SERVER_PORT = 8888


class L2Component(Enum):
    """!
    @brief Enums represent layer2 server softwares.
    """

    OP_GETH = "op-geth"
    OP_NODE = "op-node"
    OP_BATCHER = "op-batcher"
    OP_PROPOSER = "op-proposer"


class L2Account(Enum):
    """!
    @brief Enum for layer2 admin account.
    """

    GS_ADMIN = "GS_ADMIN"
    GS_BATCHER = "GS_BATCHER"
    GS_PROPOSER = "GS_PROPOSER"
    GS_SEQUENCER = "GS_SEQUENCER"


class L2Config(Enum):
    """!
    @brief Enum for layer2 configuration.
    """

    L1_RPC_URL = "L1_RPC_URL"
    L1_RPC_KIND = "L1_RPC_KIND"
    GETH_HTTP_PORT = "GETH_HTTP_PORT"
    GETH_WS_PORT = "GETH_WS_PORT"
    SEQ_RPC = "SEQ_RPC"
    DEPLOYER_URL = "DEPLOYER_URL"
    DEPLOYMENT_CONTEXT = "DEPLOYMENT_CONTEXT"


class L2Node(Enum):
    """!
    @brief Enum for layer2 server types.
    """

    NON_SEQUENCER = "l2-ns"
    SEQUENCER = "l2-seq"
    DEPLOYER = "l2-deployer"


class Layer2Template:
    """!
    @brief template class for building scripts and configurations for layer2.
    """

    __isSequencer: bool
    __components: List[L2Component]
    __ENV: Dict[str, str]
    SC_DEPLOYER: str
    __NODE_LAUNCHER: str
    __START_COMMAND: str
    __SUB_LAUNCHERS: Dict[L2Component, str]
    __GETH_CONFIG: str
    __NODE_CONFIG: str

    def __init__(self, isSequencer: bool):
        """!
        @brief Constructor for Layer2Template class.

        @param isSequencer True if the node is a sequencer.
        """
        self.__isSequencer = isSequencer
        self.__components = [L2Component.OP_GETH, L2Component.OP_NODE]
        if isSequencer:
            self.__components.extend([L2Component.OP_BATCHER, L2Component.OP_PROPOSER])
        self.__ENV = {}
        self.SC_DEPLOYER = f"""
#!/bin/bash

set -exu

source .env

# ping $L1_RPC_URL until connected
while ! curl -s $L1_RPC_URL > /dev/null
do
  sleep 5
done

# wait for L1 unitl block 5
while (( $(cast bn --rpc-url=$L1_RPC_URL) < 5 )); do
  sleep 12
done

./scripts/getting-started/config.sh

forge script scripts/Deploy.s.sol:Deploy --offline --private-key $GS_ADMIN_PRIVATE_KEY --broadcast --rpc-url $L1_RPC_URL

forge script scripts/Deploy.s.sol:Deploy --offline --sig 'sync()' --rpc-url $L1_RPC_URL

if [ -d chain_configs ]; then
  rm -rf chain_configs
fi

mkdir chain_configs

cp deployments/getting-started/L2OutputOracleProxy.json chain_configs/

./bin/op-node genesis l2 \
  --deploy-config deploy-config/getting-started.json \
  --deployment-dir deployments/getting-started/ \
  --outfile.l2 chain_configs/genesis.json \
  --outfile.rollup chain_configs/rollup.json \
  --l1-rpc $L1_RPC_URL

python3 -m http.server {WEB_SERVER_PORT} -d chain_configs
"""
        self.__NODE_LAUNCHER = """
#!/bin/bash
set -exu

source .env

# Try to retrieve genesis.json & rollup.json file from the server until it is available
while ! curl -s $DEPLOYER_URL/genesis.json > /dev/null
do
  sleep 5
done

curl -s $DEPLOYER_URL/genesis.json -o genesis.json
curl -s $DEPLOYER_URL/rollup.json -o rollup.json

# check if the files are downloaded
if [ ! -f genesis.json ] || [ ! -f rollup.json ]; then
  exit 1
fi

# check if the datadir exists
[ -d datadir ] && rm -rf datadir
mkdir datadir

# generate jwt.txt
openssl rand -hex 32 > jwt.txt

geth init --datadir=datadir genesis.json

[ -d logs ] && rm -rf logs
mkdir logs

{}
"""
        self.__START_COMMAND = "/start_{component}.sh &> logs/{component}.log &"
        self.__SUB_LAUNCHERS = {
            L2Component.OP_GETH: """
#!/bin/bash
set -eu

source .env

geth \
  --datadir ./datadir \
  --http \
  --http.corsdomain="*" \
  --http.vhosts="*" \
  --http.addr=0.0.0.0 \
  --http.port=$GETH_HTTP_PORT \
  --http.api=web3,debug,eth,txpool,net,engine \
  --ws \
  --ws.addr=0.0.0.0 \
  --ws.port=$GETH_WS_PORT \
  --ws.origins="*" \
  --ws.api=debug,eth,txpool,net,engine \
  --syncmode=full \
  --gcmode=archive \
  --nodiscover \
  --maxpeers=0 \
  --networkid=42069 \
  --authrpc.vhosts="*" \
  --authrpc.addr=0.0.0.0 \
  --authrpc.port=8551 \
  --authrpc.jwtsecret=./jwt.txt \
  --rollup.disabletxpoolgossip=true \
  --port=30304 \
  {}
""",
            L2Component.OP_NODE: """
#!/bin/bash
set -eu

source .env

op-node \
  --l2=ws://127.0.0.1:8551 \
  --l2.jwt-secret=./jwt.txt \
  --rollup.config=./rollup.json \
  --rpc.addr=0.0.0.0 \
  --rpc.port=8547 \
  --p2p.disable \
  --rpc.enable-admin \
  --l1=$L1_RPC_URL \
  --l1.rpckind=$L1_RPC_KIND \
  {}
""",
            L2Component.OP_BATCHER: """
#!/bin/bash
set -eu

source .env

op-batcher \
  --l2-eth-rpc=http://127.0.0.1:$GETH_HTTP_PORT \
  --rollup-rpc=http://127.0.0.1:8547 \
  --poll-interval=1s \
  --sub-safety-margin=6 \
  --num-confirmations=1 \
  --safe-abort-nonce-too-low-count=3 \
  --resubmission-timeout=30s \
  --rpc.addr=0.0.0.0 \
  --rpc.port=8548 \
  --rpc.enable-admin \
  --max-channel-duration=1 \
  --l1-eth-rpc=$L1_RPC_URL \
  --private-key=$GS_BATCHER_PRIVATE_KEY
""",
            L2Component.OP_PROPOSER: """
#!/bin/bash
set -eu

source .env

curl -s $DEPLOYER_URL/L2OutputOracleProxy.json -o /L2OutputOracleProxy.json

op-proposer \
  --poll-interval=12s \
  --rpc.addr=0.0.0.0 \
  --rpc.port=8560 \
  --rollup-rpc=http://127.0.0.1:8547 \
  --l2oo-address=$(cat /L2OutputOracleProxy.json | jq -r .address) \
  --private-key=$GS_PROPOSER_PRIVATE_KEY \
  --l1-eth-rpc=$L1_RPC_URL \
  --allow-non-finalized=true \
  --log.level=debug
""",
        }
        self.__GETH_CONFIG = "--rollup.sequencerhttp=$SEQ_RPC"
        self.__NODE_CONFIG = "--sequencer.enabled --sequencer.l1-confs=5 --verifier.l1-confs=4 --p2p.sequencer.key=$GS_SEQUENCER_PRIVATE_KEY"

    def getNodeLauncher(self) -> str:
        """!
        @brief Get the layer2 server starting script.

        @return The layer2 server starting script.
        """
        startCommands = [
            self.__START_COMMAND.format(component=component.value)
            for component in self.__components
        ]
        return self.__NODE_LAUNCHER.format("\n".join(startCommands))

    def getComponents(self) -> List[L2Component]:
        """!
        @brief Get the softwares which this instance is building for their scripts.

        @return The list of softwares.
        """
        return self.__components

    def getSubLauncher(self, component: L2Component) -> str:
        """!
        @brief Get the start script of the software.

        @param component The software enum.

        @return The start script of the software.
        """
        if component == L2Component.OP_GETH:
            content = self.__GETH_CONFIG if not self.__isSequencer else ""
            return self.__SUB_LAUNCHERS[component].format(content)
        elif component == L2Component.OP_NODE:
            content = self.__NODE_CONFIG if self.__isSequencer else ""
            return self.__SUB_LAUNCHERS[component].format(content)

        return self.__SUB_LAUNCHERS[component]

    def setEnv(self, env: Dict[str, str]) -> Layer2Template:
        """!
        @brief Add the environment variable.

        @param env The environment variable

        @return The instance itself, for chaining.
        """
        self.__ENV.update(env)

        return self

    def getEnvs(self) -> List[Dict[str, str]]:
        """!
        @brief Get all the environment variables.

        @return The environment variables.
        """
        return self.__ENV

    def exportEnvFile(self) -> str:
        """!
        @brief Construct and export the environment file.

        @return The environment file content.
        """

        return "\n".join([f"{key}={value}" for key, value in self.__ENV.items()])

    def setAccountEnv(self, accType: L2Account, acc: str, sk: str) -> Layer2Template:
        """!
        @brief Set the account environment variables.

        @param accType The account type
        @param acc The account address
        @param sk The account private key

        @return The instance itself, for chaining.
        """

        self.__ENV[f"{accType.value}_ADDRESS"] = acc
        self.__ENV[f"{accType.value}_PRIVATE_KEY"] = sk

        return self
