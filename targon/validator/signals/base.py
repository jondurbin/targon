import torch
import bittensor as bt
from typing import List
from abc import abstractmethod

class BaseRewardModel:

    @property
    @abstractmethod
    def name(self) -> str: ...
    def __str__(self) -> str: return str(self.name)
    def __repr__(self) -> str: return str(self.name)

    @abstractmethod
    def get_rewards( self, prompt: str, completion: List[str] ) -> torch.FloatTensor: ...

    def __init__(self) -> None:
        self.count = 0
        self.mean = 0.0
        self.var = 0.0
        self.count_limit = 3000

    def normalize_rewards(self, rewards: torch.FloatTensor) -> torch.FloatTensor:
        # Update stats only if there are new rewards.
        new_count = rewards.numel()
        if new_count > 0 and self.count + new_count > 0:
            new_mean = rewards.mean()
            new_var = rewards.var(dim=0)
            new_weight = new_count / (self.count + new_count)
            old_weight = self.count / (self.count + new_count)
            diff = new_mean - self.mean
            self.mean = new_weight * new_mean + old_weight * self.mean
            self.var = (new_weight * new_var) + (old_weight * self.var) + (new_weight * old_weight) * diff * diff
            self.count = min(self.count_limit, self.count + new_count)

        # Standardize the rewards.
        standardized_rewards = rewards - self.mean
        if self.var > 0:
            standardized_rewards /= torch.sqrt(self.var)

        # Desired range
        min_desired = 0.2
        max_desired = 8.0

        # Find the min and max in the current rewards
        min_current = rewards.min()
        max_current = rewards.max()

        # Normalize the rewards to the 0-1 range
        normalized_rewards = (rewards - min_current) / (max_current - min_current)

        # Scale to the desired range
        scaled_rewards = normalized_rewards * (max_desired - min_desired) + min_desired



        return scaled_rewards

    def apply( self, prompt: str, responses: List[ str ]) -> torch.FloatTensor:
        """ Applies the reward model across each call. Unsuccessful responses are zeroed.
        """
        # Get indices of correctly responding calls.
        def standardization_transformation(rewards):
            # Standardization
            standardized_rewards = (rewards - rewards.mean()) / rewards.std()

            # Min-Max scaling to the range [0, 1]
            min_val = standardized_rewards.min()
            max_val = standardized_rewards.max()
            min_max_scaled_rewards = (standardized_rewards - min_val) / (max_val - min_val)

            return min_max_scaled_rewards
        successful_completions_indices: List[int] = [ idx for idx, resp in enumerate(responses) if resp != "" ]

        # Get all completions from responding calls.
        successful_completions: List[str] = [ responses[idx].strip() for idx in successful_completions_indices]

        # Reward each completion.
        successful_rewards = self.get_rewards( prompt, successful_completions )

        # Softmax rewards across samples.
        successful_rewards_normalized = self.normalize_rewards( successful_rewards )

        successful_rewards = standardization_transformation(successful_rewards)
        successful_rewards_normalized = standardization_transformation(successful_rewards_normalized)
        
        # Init zero rewards for all calls.
        filled_rewards = torch.ones( len( responses ), dtype=torch.float32) * torch.nan
        filled_rewards_normalized = torch.zeros( len( responses ), dtype=torch.float32)


        # Fill reward tensor.
        for idx, reward, reward_normalized in zip(successful_completions_indices, successful_rewards, successful_rewards_normalized):
            filled_rewards[idx] = reward
            filled_rewards_normalized[idx] = reward_normalized

        # Return the filled rewards.
        return filled_rewards, filled_rewards_normalized


class MockRewardModel( BaseRewardModel ):

    @property
    def name(self) -> str: return self.mock_name

    def __init__(self, mock_name: str = 'MockReward'):
        super().__init__()
        self.mock_name = mock_name

    def apply( self, prompt: str, completion: List[str], name: str ) -> torch.FloatTensor: 
        mock_reward = torch.tensor( [0 for _ in completion], dtype=torch.float32 )
        return mock_reward, mock_reward

        