from flask import Blueprint, request, jsonify
from ..utils import step
from ..config import ORDER

process_bp = Blueprint('process', __name__)
step_count = {}


@process_bp.route('/upload', methods=['GET'])
def upload():
    lights = request.args.get('lights', default=[], type='list')
    darks = request.args.get('darks', default=[], type='list')
    flats = request.args.get('flats', default=[], type='list')
    bias = request.args.get('bias', default=[], type='list')


@process_bp.route('/execute', methods=['GET', 'POST'])
def execute():
    subproc_configs = request.args.get('algos', default=[], type='list')

    subprocs = []
    for config in subproc_configs:
        subproc = build_algo(config)
        subprocs.append(subproc)

    step_count = step(step_count)
    step_num = step_count['count']
    Process = ORDER[step_num]
    proc = Process(subprocs)

    return proc.execute(ccd)
