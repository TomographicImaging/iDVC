#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at

#   http://www.apache.org/licenses/LICENSE-2.0

#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

#   Author: Danica sugic (UKRI-STFC)

import numpy as np

def extract_point_cloud_from_inp_file(inp_file_path):
    with open(inp_file_path, 'r') as inpDeck:
        lines = [ln.strip() for ln in inpDeck.readlines()]
        lines = [ln for ln in lines if not ln.startswith("**")]
        n_nodes= int([n for n, ln in enumerate(lines) if ln.startswith("*NODE")][0])
        n_next= int([n + n_nodes+ 1 for n, ln in enumerate(lines[n_nodes+1:]) if ln.startswith("*")][0])
        nodes = []
        for ln in lines[n_nodes+1:n_next]:
            idx, x, y, z = ln.split(",")
            nodes.append((int(idx.strip()), float(x.strip()), float(y.strip()), float(z.strip())))
        nodes = np.array(nodes)
    return nodes