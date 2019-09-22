#######################################################################
# Copyright (C) 2017 Shangtong Zhang(zhangshangtong.cpp@gmail.com)    #
# Permission given to modify the code as long as you keep this        #
# declaration at the top                                              #
#######################################################################

import os
import gym
import numpy as np
import torch
from gym.spaces.box import Box
from gym.spaces.discrete import Discrete

from baselines.common.atari_wrappers import make_atari, wrap_deepmind
from baselines.common.atari_wrappers import FrameStack as FrameStack_
from baselines.common.vec_env.subproc_vec_env import SubprocVecEnv, VecEnv

from ..utils import *

try:
    import roboschool
except ImportError:
    pass


# adapted from https://github.com/ikostrikov/pytorch-a2c-ppo-acktr/blob/master/envs.py
def make_env(env_id, seed, rank, episode_life=True):
    def _thunk():
        # I think this is not needed
        # random_seed(seed)
        if env_id.startswith("dm"):
            import dm_control2gym
            _, domain, task = env_id.split('-')
            env = dm_control2gym.make(domain_name=domain, task_name=task)
        else:
            # My code for reacher env:
            if env_id == 'reacher':
                env = make_reacher()
            elif env_id == 'tennis':
                env = make_tennis()
            else:
                env = gym.make(env_id)

        is_atari = hasattr(gym.envs, 'atari') and isinstance(
            env.unwrapped, gym.envs.atari.atari_env.AtariEnv)
        if is_atari:
            env = make_atari(env_id)
        env.seed(seed + rank)
        env = OriginalReturnWrapper(env)
        if is_atari:
            env = wrap_deepmind(env,
                                episode_life=episode_life,
                                clip_rewards=False,
                                frame_stack=False,
                                scale=False)
            obs_shape = env.observation_space.shape
            if len(obs_shape) == 3:
                env = TransposeImage(env)
            env = FrameStack(env, 4)

        return env

    return _thunk


class TennisVecEnv(gym.Env):

    reward_range = (-0.01, 0.1)

    def __init__(self):
        from unityagents import UnityEnvironment

        env = UnityEnvironment(file_name='Tennis_Linux/Tennis.x86_64')

        # get the default brain
        brain_name = env.brain_names[0]
        brain = env.brains[brain_name]

        self.train_mode = True

        # reset the environment
        env_info = env.reset(train_mode=self.train_mode)[brain_name]

        # number of agents
        num_agents = len(env_info.agents)
        print('Number of agents:', num_agents)

        # size of each action
        action_size = brain.vector_action_space_size
        print('Size of each action:', action_size)

        # examine the state space
        states = env_info.vector_observations
        state_size = states.shape[1]
        print('There are {} agents. Each agent observes state size: {}'.format(states.shape[0], state_size))
        print('The state for the first agent looks like:', states[0])

        self.unity_env = env
        self.brain_name = brain_name
        self.brain = brain

        # # action vector is between -1 and +1
        action_space = np.array(np.ones(action_size))
        # # 100 is a guess from me ;-)
        state_space = np.array(np.full(state_size, fill_value=100))

        # # Need to be set
        self.action_space = Box(-action_space, action_space, dtype=np.float32)
        self.observation_space = Box(-state_space, state_space, dtype=np.float32)

        self.last_step = None

    def step_both_agents(self, actions):
        env_info = self.unity_env.step(actions)[self.brain_name]
        state = env_info.vector_observations  # get the current state
        reward = env_info.rewards  # get the reward
        done = env_info.local_done  # see if episode has finished

        return state, reward, done, {}

    def step(self, action):
        return self.step_both_agents(action)
        # raise NotImplementedError('Cannot step for a single agent!')

    def reset(self):
        env_info = self.unity_env.reset(train_mode=self.train_mode)[self.brain_name]
        return env_info.vector_observations  # Return current state

    def close(self):
        self.unity_env.close()

    def render(self, mode='human'):
        # no-op
        raise NotImplementedError()

    def seed(self, seed=None):
        # no-op
        return [0]


class TennisSingleAgentWrapper(gym.Env):

    metadata = {
        # 'render.modes': ['human'],
        'render.modes': [],
    }

    reward_range = (-0.01, 0.1)

    def __init__(self, tennis_single_env: TennisVecEnv, agent_number):
        assert agent_number in (0, 1)
        print("Creating for agent ", agent_number)

        self.tennis_single_env = tennis_single_env

        self.train_mode = True

        # size of each action
        action_size = tennis_single_env.action_size[1]
        print('Size of each action:', action_size)

        # examine the state space
        state_size = tennis_single_env.state_size[1]
        print('This agent observes a state with length: ', state_size)

        # todo: is the action vector really between -1 and +1? not documented ..
        # # action vector is between -1 and +1
        action_space = np.array([1] * action_size)
        # # 100 is a guess from me ;-)
        state_space = np.array([100] * state_size)
        #
        # # Need to be set
        self.action_space = Box(-action_space, action_space, dtype=np.float32)
        self.observation_space = Box(-state_space, state_space, dtype=np.float32)

        print('(gym) action space: ', self.action_space)
        print('(gym) observation space: ', self.observation_space)

    # todo: split actions, states, rewards and dones into 2, one for each agent
    # create another object, holding the actual env
    # and two objects handling agent 0 and agent 1.
    # > two make calls should be done for train tasks
    # plus, one for eval.. however eval will not work so i have to re-write to use both agents somehow..
    # Probably: combine outputs from both agents and feed them into the "main" environment

    def step(self, action):
        # todo..
        # state_both, reward_both_

        return state, reward, done, {}

    # this would reset twice..
    def reset(self):
        return self.tennis_single_env.reset()

    def render(self, mode='human'):
        # no-op
        raise NotImplementedError()

    def seed(self, seed=None):
        # no-op
        return [0]

    # wrong, second call will fail
    def close(self):
        self.tennis_single_env.close()

    @property
    def train_mode(self):
        return self.tennis_single_env.train_mode

    @train_mode.setter
    def train_mode(self, train_mode):
        self.tennis_single_env.train_mode = train_mode


_tennis_vec_env_instance = None
_tennis_instace_counter = 0


def make_tennis():
    global _tennis_vec_env_instance
    if not _tennis_vec_env_instance:
        _tennis_vec_env_instance = TennisVecEnv()
    return _tennis_vec_env_instance


_reacher_instance = None


def make_reacher():
    global _reacher_instance
    if not _reacher_instance:
        _reacher_instance = ReacherWrapper()
    return _reacher_instance


class ReacherWrapper(gym.Env):

    metadata = {
        # 'render.modes': ['human'],
        'render.modes': [],
    }

    reward_range = (0., 0.1)

    def __init__(self):
        from unityagents import UnityEnvironment

        env = UnityEnvironment(file_name='Reacher_Linux/Reacher.x86_64')

        # get the default brain
        brain_name = env.brain_names[0]
        brain = env.brains[brain_name]

        self.train_mode = True

        # reset the environment
        env_info = env.reset(train_mode=self.train_mode)[brain_name]

        # number of agents
        num_agents = len(env_info.agents)
        #print('Number of agents:', num_agents)

        # size of each action
        action_size = brain.vector_action_space_size
        #print('Size of each action:', action_size)

        # examine the state space
        states = env_info.vector_observations
        state_size = states.shape[1]
        #print('There are {} agents. Each observes a state with length: {}'.format(states.shape[0], state_size))
        #print('The state for the first agent looks like:', states[0])

        self.unity_env = env
        self.brain_name = brain_name

        # action vector is between -1 and +1
        action_space = np.array([1] * brain.vector_action_space_size)
        # 100 is a guess from me ;-)
        state_space = np.array([100] * brain.vector_observation_space_size)

        # Need to be set
        self.action_space = Box(-action_space, action_space, dtype=np.float32)
        self.observation_space = Box(-state_space, state_space, dtype=np.float32)

    def step(self, action):
        env_info = self.unity_env.step(action)[self.brain_name]
        state = env_info.vector_observations[0]  # get the current state
        reward = env_info.rewards[0]  # get the reward
        done = env_info.local_done[0]  # see if episode has finished

        return state, reward, done, {}

    def reset(self):
        env_info = self.unity_env.reset(train_mode=self.train_mode)[self.brain_name]
        return env_info.vector_observations[0]  # Return current state

    def render(self, mode='human'):
        # no-op
        raise NotImplementedError()

    def seed(self, seed=None):
        # no-op
        return [0]

    def close(self):
        self.unity_env.close()


class OriginalReturnWrapper(gym.Wrapper):
    def __init__(self, env):
        gym.Wrapper.__init__(self, env)
        self.total_rewards = 0

    def step(self, action):
        obs, reward, done, info = self.env.step(action)
        self.total_rewards += sum(reward)
        if any(done):
            info['episodic_return'] = self.total_rewards
            self.total_rewards = 0
            obs = self.env.reset()  # reset if any agent reports done
        else:
            info['episodic_return'] = None
        return obs, reward, done, (info, info)

    def reset(self):
        return self.env.reset()


class TransposeImage(gym.ObservationWrapper):
    def __init__(self, env=None):
        super(TransposeImage, self).__init__(env)
        obs_shape = self.observation_space.shape
        self.observation_space = Box(
            self.observation_space.low[0, 0, 0],
            self.observation_space.high[0, 0, 0],
            [obs_shape[2], obs_shape[1], obs_shape[0]],
            dtype=self.observation_space.dtype)

    def observation(self, observation):
        return observation.transpose(2, 0, 1)


# The original LayzeFrames doesn't work well
class LazyFrames(object):
    def __init__(self, frames):
        """This object ensures that common frames between the observations are only stored once.
        It exists purely to optimize memory usage which can be huge for DQN's 1M frames replay
        buffers.

        This object should only be converted to numpy array before being passed to the model.

        You'd not believe how complex the previous solution was."""
        self._frames = frames

    def __array__(self, dtype=None):
        out = np.concatenate(self._frames, axis=0)
        if dtype is not None:
            out = out.astype(dtype)
        return out

    def __len__(self):
        return len(self.__array__())

    def __getitem__(self, i):
        return self.__array__()[i]


class FrameStack(FrameStack_):
    def __init__(self, env, k):
        FrameStack_.__init__(self, env, k)

    def _get_ob(self):
        assert len(self.frames) == self.k
        return LazyFrames(list(self.frames))


# The original one in baselines is really bad
class DummyVecEnv(VecEnv):
    def __init__(self, env_fns):
        self.envs = [fn() for fn in env_fns]
        env = self.envs[0]
        VecEnv.__init__(self, len(env_fns), env.observation_space, env.action_space)
        self.actions = None

    def step_async(self, actions):
        self.actions = actions

    def step_wait(self):
        data = []
        for i in range(self.num_envs):
            obs, rew, done, info = self.envs[i].step(self.actions[i])
            if done:
                obs = self.envs[i].reset()
            data.append([obs, rew, done, info])
        obs, rew, done, info = zip(*data)
        return obs, np.asarray(rew), np.asarray(done), info

    def reset(self):
        return [env.reset() for env in self.envs]

    def close(self):
        return


class Task:
    def __init__(self,
                 name,
                 num_envs=1,
                 single_process=True,
                 log_dir=None,
                 episode_life=True,
                 seed=np.random.randint(int(1e5))):
        if log_dir is not None:
            mkdir(log_dir)

        if name == 'tennis':
            self.env = OriginalReturnWrapper(TennisVecEnv())
        else:
            envs = [make_env(name, seed, i, episode_life) for i in range(num_envs)]
            if single_process:
                Wrapper = DummyVecEnv
            else:
                Wrapper = SubprocVecEnv
            self.env = Wrapper(envs)

        self.name = name
        self.observation_space = self.env.observation_space
        self.state_dim = int(np.prod(self.env.observation_space.shape))

        self.action_space = self.env.action_space
        if isinstance(self.action_space, Discrete):
            self.action_dim = self.action_space.n
        elif isinstance(self.action_space, Box):
            self.action_dim = self.action_space.shape[0]
        else:
            assert 'unknown action space'

    def reset(self):
        return self.env.reset()

    def step(self, actions):
        if isinstance(self.action_space, Box):
            actions = np.clip(actions, self.action_space.low, self.action_space.high)
        return self.env.step(actions)


if __name__ == '__main__':
    task = Task('Hopper-v2', 5, single_process=False)
    state = task.reset()
    while True:
        action = np.random.rand(task.observation_space.shape[0])
        next_state, reward, done, _ = task.step(action)
        print(done)
