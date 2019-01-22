# Copyright (C) 2019  Collin Capano
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 3 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from __future__ import absolute_import

import numpy

import epsie
from epsie import create_seed, create_brngs
from .chain import Chain
from .proposals import Normal


def _run(niterations_chain):
    """Private method for evolving the chains."""
    niterations, chain = niterations_chain
    for _ in range(niterations):
        chain.step()
    return chain

class Sampler(object):
    """
    Parameters
    ----------
    parameters : tuple or list
        Names of the parameters to sample.
    model : object
        Model object.
    nchains : int
        The number of chains to create.
    proposals : dict, optional
        Dictionary mapping parameter names to proposal classes. Any parameters
        not listed will use the ``default_propsal``.
    default_proposal : an epsie.Proposal class, optional
        The default proposal to use for parameters not in ``proposals``.
        Default is :py:class:`epsie.proposals.Normal`.
    seed : int, optional
        Seed for the random number generator. If None provided, will create
        one.
    pool : Pool object, optional
        Specify a process pool to use for parallelization. Default is to use a
        single core.
    """
        

    def __init__(self, parameters, model, nchains, proposals=None,
                 default_proposal=None, seed=None, pool=None):
        self.parameters = tuple(parameters)
        self.model = model
        self.nchains = nchains
        if proposals is None:
            proposals = {}
        # create default proposal instances for the other parameters
        if default_proposal is None:
            default_proposal = Normal
        missing_props =  tuple(set(parameters) - set(proposals.keys()))
        proposals[missing_props] = default_proposal(missing_props)
        self.proposals = proposals
        self.niterations = 0
        # create the random number states
        if seed is None:
            seed = create_seed(seed)
        self.seed = seed
        # create the chains
        self.chains = [Chain(self.parameters, self.model,
                             self.proposals.values(),
                             brng=epsie.create_brng(self.seed, stream=cid),
                             chain_id=cid)
                       for cid in range(self.nchains)]
        # set the mapping function
        if pool is None:
            self.map = map
        else:
            self.map = pool.map

    def set_start(self, positions):
        """Sets the starting position of all of the chains.

        Parameters
        ----------
        positions : dict
            Dictionary mapping parameter names to arrays of values. The chains
            must have length equal to the number of chains.
        """
        for (ii, chain) in enumerate(self.chains):
            chain.set_start({p: positions[p][ii] for p in positions})

    def clear(self):
        """Clears all of the chains."""
        for chain in self.chains:
            chain.clear()

    def run(self, niterations):
        """Evolves all of the chains by niterations.

        Parameters
        ----------
        niterations : int
            The number of iterations to evolve the chains for.
        """
        args = zip([niterations]*len(self.chains), self.chains)
        self.chains = self.map(_run, args)
            #lambda x: self._run(niterations, x), self.chains)

    @staticmethod
    def _run(niterations, chain):
        """Private method for evolving the chains."""
        for _ in range(niterations):
            chain.step()
        return chain

    def concatenate_chains(self, attr, item=None):
        """Concatenates the given attribute over all of the chains."""
        if item is None:
            getter = lambda x: getattr(x, attr)
        else:
            getter = lambda x: getattr(x, attr)[item]
        return numpy.stack(map(getter, self.chains), axis=0)

    @property
    def start_position(self):
        """The start position of the chains.
        
        Will raise a ``ValueError`` is ``set_start`` hasn't been run.

        Returns
        -------
        dict :
            Dictionary mapping parameters to arrays with shape ``nchains``
            giving the starting position of each chain.
        """
        #return {p: numpy.array([c.start_position[p] for c in self.chains])
        #        for p in self.parameters}
        return {p: self.concatenate_chains('start_position', p)
                for p in self.parameters}

    @property
    def positions(self):
        """The history of positions from all of the chains."""
        return {p: self.concatenate_chains('positions', p)
                for p in self.parameters}

    @property
    def stats(self):
        """The history of stats from all of the chains."""
        return {s: self.concatenate_chains('stats', s)
                for s in ['logl', 'logp']}

    @property
    def blobs(self):
        """The history of all of the blobs from all of the chains."""
        if self.chains[0].hasblobs:
            blobs = {b: self.concatenate_chains('blobs', b)
                     for b in self.chains[0].blob0}
        else:
            blobs = None
        return blobs

    @property
    def acceptance_ratios(self):
        """The history of all acceptance ratios from all of the chains."""
        return self.concatenate_chains('acceptance_ratio')
