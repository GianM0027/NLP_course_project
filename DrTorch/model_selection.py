"""



 /$$$$$$$         /$$$$$$$$                            /$$
| $$__  $$       |__  $$__/                           | $$
| $$  \ $$  /$$$$$$ | $$  /$$$$$$   /$$$$$$   /$$$$$$$| $$$$$$$
| $$  | $$ /$$__  $$| $$ /$$__  $$ /$$__  $$ /$$_____/| $$__  $$
| $$  | $$| $$  \__/| $$| $$  \ $$| $$  \__/| $$      | $$  \ $$
| $$  | $$| $$      | $$| $$  | $$| $$      | $$      | $$  | $$
| $$$$$$$/| $$      | $$|  $$$$$$/| $$      |  $$$$$$$| $$  | $$
|_______/ |__/      |__/ \______/ |__/       \_______/|__/  |__/



"""

import inspect

from IPython.utils.capture import capture_output
from contextlib import redirect_stdout
from io import StringIO

from .wrappers import Criterion, OptimizerWrapper
from .metrics import Metric
from .callbacks import EarlyStopper
from .utilities import DataLoaderStrategy

import torch

import wandb
import joblib
import numpy as np
import pandas as pd

from tqdm import tqdm
import itertools
import time

from typing import Any, Optional, Tuple, List, Dict

FIT_PARAMETER_TYPES = torch.utils.data.DataLoader | torch.utils.data.DataLoader | Criterion | list[Metric] | \
                      OptimizerWrapper | int | Optional[EarlyStopper] | bool


def grid_search_train_validation(train_data: Tuple[torch.Tensor, torch.Tensor] | Tuple[pd.DataFrame, pd.DataFrame],
                                 val_data: Tuple[torch.Tensor, torch.Tensor] | Tuple[pd.DataFrame, pd.DataFrame],
                                 dataloader_builder: DataLoaderStrategy,
                                 shuffle: bool,
                                 model_hyperparameters_to_test: List[Dict[str, Any]],
                                 training_hyperparameters_to_test: List[Dict[str, FIT_PARAMETER_TYPES]],
                                 hyperparameters_key_to_save: List[str],
                                 device: str,
                                 path_to_grid_search_results: str,
                                 seeds: Optional[List[int]] = None,
                                 save_loss_values: bool = False,
                                 wandb_params: Optional[Dict[str, str]] = None) -> pd.DataFrame:
    """
    Perform a grid search train validation over a combination of model and training hyperparameters for a
    deep learning model.

    :param train_data: A tuple containing training data (input and labels).
    :param val_data: A tuple containing validation data (input and labels).
    :param dataloader_builder: A callable function to build a PyTorch DataLoader.
    :param shuffle: A boolean flag indicating whether to shuffle the data during training.
    :param model_hyperparameters_to_test: A list of dictionaries, each specifying model hyperparameters to test.
    :param training_hyperparameters_to_test: A list of dictionaries, each specifying training hyperparameters to test.
    :param hyperparameters_key_to_save: A list of hyperparameter keys to save in the result dataframe.
    :param device: The device (e.g., 'cpu' or 'cuda:0') to run the model training on.
    :param path_to_grid_search_results: Path to the file storing the grid search results.
    :param seeds: List of the seeds for reproducibility of the results of the grid search.
    :param save_loss_values: If True save train and val loss values.
    :param wandb_params: Additional parameters for WandB integration(e.g {'project': project, 'entity': userName}).

    :return: A pandas DataFrame containing the results of the grid search, including hyperparameters and performance metrics.

    :Example:
        #todo example
    """

    iterator = tqdm(
        iterable=enumerate(itertools.product(training_hyperparameters_to_test, model_hyperparameters_to_test)),
        total=len(training_hyperparameters_to_test) * len(model_hyperparameters_to_test))

    return collect_results(train_data=train_data,
                           val_data=val_data,
                           dataloader_builder=dataloader_builder,
                           iterator=iterator,
                           shuffle=shuffle,
                           device=device,
                           hyperparameters_key_to_save=hyperparameters_key_to_save,
                           path_to_results=path_to_grid_search_results,
                           seeds=seeds,
                           save_loss_values=save_loss_values,
                           wandb_params=wandb_params)


def randomized_search_train_validation(
        train_data: Tuple[torch.Tensor, torch.Tensor] | Tuple[pd.DataFrame, pd.DataFrame],
        val_data: Tuple[torch.Tensor, torch.Tensor] | Tuple[pd.DataFrame, pd.DataFrame],
        dataloader_builder: DataLoaderStrategy,
        shuffle: bool,
        model_hyperparameters_to_sample: Dict[str, Any],
        training_hyperparameters_to_sample: Dict[str, Any],
        hyperparameters_key_to_save: List[str],
        n_run: int,
        device: str,
        path_to_randomized_search_results: str,
        seeds: Optional[List[int]] = None,
        save_loss_values: bool = False,
        wandb_params: Optional[Dict[str, str]] = None) -> pd.DataFrame:
    """
    Perform a randomize search train validation over a combination of model and training hyperparameters for a
    deep learning model.

    :param train_data: Tuple containing training input data and labels.
    :param val_data: Tuple containing validation input data and labels.
    :param dataloader_builder: A callable function to build a PyTorch DataLoader.
    :param shuffle: Boolean indicating whether to shuffle the data during training.
    :param model_hyperparameters_to_sample: Dictionary of model hyperparameter names and functions to sample values.
    :param training_hyperparameters_to_sample: Dictionary of training hyperparameter names and functions to sample values.
    :param hyperparameters_key_to_save: List of hyperparameter names to save in the resulting DataFrame.
    :param n_run: Number of runs for the randomized search.
    :param device: Device on which to perform the training (e.g., 'cpu' or 'cuda:0').
    :param path_to_randomized_search_results: path to the file storing the randomized search results.
    :param seeds: List of the seeds for reproducibility of the results of the grid search.
    :param save_loss_values: If True save train and val loss values.
    :param wandb_params: Additional parameters for WandB integration(e.g {'project': project, 'entity': userName}).

    :return: DataFrame containing the results of the randomized search.

    :Example: .... #todo bisogna inserire gli esempi per descrive i modi in cui si può utilizzare

    """

    model_hyperparameters_to_test = []
    training_hyperparameters_to_test = []

    i = 0

    while i < n_run:
        model_d = {}
        training_d = {}
        for key, sampler in model_hyperparameters_to_sample.items():
            model_d[key] = sampler()
        for key, sampler in training_hyperparameters_to_sample.items():
            training_d[key] = sampler()

        model_hyperparameters_already_present = np.any([model_d == mc for mc in model_hyperparameters_to_test])
        training_hyperparameters_already_present = np.any([training_d == tc for tc in training_hyperparameters_to_test])

        if not (model_hyperparameters_already_present and training_hyperparameters_already_present):
            model_hyperparameters_to_test.append(model_d)
            training_hyperparameters_to_test.append(training_d)
            i += 1

    iterator = tqdm(iterable=enumerate(zip(training_hyperparameters_to_test, model_hyperparameters_to_test)),
                    total=len(training_hyperparameters_to_test))

    return collect_results(train_data=train_data,
                           val_data=val_data,
                           dataloader_builder=dataloader_builder,
                           iterator=iterator,
                           shuffle=shuffle,
                           device=device,
                           hyperparameters_key_to_save=hyperparameters_key_to_save,
                           path_to_results=path_to_randomized_search_results,
                           seeds=seeds,
                           save_loss_values=save_loss_values,
                           wandb_params=wandb_params)


def collect_results(train_data: Tuple[torch.Tensor, torch.Tensor] | Tuple[pd.DataFrame, pd.DataFrame],
                    val_data: Tuple[torch.Tensor, torch.Tensor] | Tuple[pd.DataFrame, pd.DataFrame],
                    dataloader_builder: DataLoaderStrategy,
                    iterator: Any,
                    shuffle: bool,
                    device: str,
                    hyperparameters_key_to_save: List[str],
                    path_to_results: str,
                    seeds: Optional[List[int]] = None,
                    save_loss_values: bool = False,
                    wandb_params: Optional[dict[str, str]] = None) -> pd.DataFrame:
    """
    Collects and stores results from multiple runs of a training process.

    :param train_data: Tuple containing training input and labels tensors or dataframes.
    :param val_data: Tuple containing validation input and labels tensors or dataframes.
    :param dataloader_builder:  An instance of DataLoaderStrategy for creating data loaders.
    :param iterator: An iterable representing the range of runs or configurations to be tested.
    :param shuffle: Boolean indicating whether to shuffle the data during training.
    :param device: The device on which the model should be trained ('cpu' or 'cuda').
    :param hyperparameters_key_to_save: List of hyperparameter keys to save in the results dataframe.
    :param path_to_results: Path to store the results dataframe.
    :param seeds: List of seed values for reproducibility.
    :param save_loss_values: If True save train and val loss values.
    :param wandb_params: Additional parameters for WandB integration(e.g {'project': project, 'entity': userName}).

    :return: DataFrame containing collected results.

    """
    test_iterator = seeds if seeds is not None else range(1)

    train_input, train_labels = train_data
    val_input, val_labels = val_data
    dataframe_dict = {key: [] for key in hyperparameters_key_to_save}
    dataframe_dict['time'] = []
    dataframe_dict['seed'] = []
    if save_loss_values:
        dataframe_dict['train_loss'] = []
        dataframe_dict['val_loss'] = []

    if wandb_params is not None:
        wandb_flags = ['interaction_with_wandb']
    else:
        wandb_flags = []

    run_idx = 0

    for n_run, (training_hyperparameters, model_hyperparameters) in iterator:

        criterion = training_hyperparameters['criterion']

        early_stopper_exist = 'early_stopper' in training_hyperparameters and training_hyperparameters[
            'early_stopper'] is not None
        history_idx = -1
        if early_stopper_exist:
            history_idx -= training_hyperparameters['early_stopper'].patience

        if wandb_params is not None and not any([flag in training_hyperparameters for flag in wandb_flags]):
            warning_message = '''Warning: Wandb connection started without logging anything.Maybe you want to add some training hyperparameters wandb related:'''
            print('\n'.join([warning_message] + wandb_flags))

        total_hyperparameters = {**training_hyperparameters, **model_hyperparameters}

        dataloader_params = [key for key in inspect.signature(dataloader_builder.create).parameters.keys()]
        dataloader_params = [element for element in dataloader_params if
                             element not in ['data', 'labels', 'shuffle', 'device']]
        dataloader_params = {param: total_hyperparameters[
            param] if param in total_hyperparameters else dataloader_builder.get_dataloader_params(param,
                                                                                                   total_hyperparameters)
                             for param in dataloader_params}

        train_data_loader = dataloader_builder.create(data=train_input,
                                                      labels=train_labels,
                                                      shuffle=shuffle,
                                                      device=device,
                                                      **dataloader_params)

        val_data_loader = dataloader_builder.create(data=val_input,
                                                    labels=val_labels,
                                                    shuffle=False,
                                                    device=device,
                                                    **dataloader_params)

        new_training_hyperparameters = training_hyperparameters.copy()
        new_training_hyperparameters.pop('batch_size')

        train_results = dict()
        val_results = dict()

        train_results[criterion.name] = []
        val_results[criterion.name] = []

        for metric in training_hyperparameters.get('metrics', []):
            train_results[metric.name] = []
            val_results[metric.name] = []

        fitting_times = []

        for idx, test_iteration in enumerate(test_iterator):

            if wandb_params is not None:
                config_params = {key: total_hyperparameters[key] for key in hyperparameters_key_to_save}
            else:
                config_params = {}

            if seeds is not None:
                torch.manual_seed(test_iteration)
                np.random.seed(test_iteration)
                if wandb_params is not None:
                    config_params['seed'] = test_iteration

            new_model_hyperparameters = model_hyperparameters.copy()
            new_model_hyperparameters.pop('model_class')
            net = model_hyperparameters['model_class'](**new_model_hyperparameters).to(device)
            if wandb_params is not None:
                captured_output = StringIO()
                with capture_output() as captured:
                    with redirect_stdout(captured_output):
                        wandb.init(config=config_params, name=f'run_{run_idx}', **wandb_params)
                wandb.watch(net, total_hyperparameters['criterion'], log="all", log_graph=True)

            start_time = time.time()
            result = net.fit(train_loader=train_data_loader,
                             val_loader=val_data_loader,
                             verbose=False,
                             **new_training_hyperparameters)
            end_time = time.time()
            fitting_times.append(end_time - start_time)

            train_results[criterion.name].append(result['train'][criterion.name][history_idx])
            val_results[criterion.name].append(result['val'][criterion.name][history_idx])

            for metric in training_hyperparameters.get('metrics', []):
                train_results[metric.name].append(result['train'][metric.name][history_idx])
                val_results[metric.name].append(result['val'][metric.name][history_idx])

            run_idx += 1

        for key in hyperparameters_key_to_save:
            dataframe_dict[key].append(total_hyperparameters[key])

        for i, seed in enumerate(seeds):
            dataframe_dict['seed'].append(seed)
            dataframe_dict['time'].append(fitting_times[i])

            if save_loss_values:
                dataframe_dict['train_loss'].append(train_results[criterion.name][i])
                dataframe_dict['val_loss'].append(val_results[criterion.name][i])

            for metric in training_hyperparameters.get('metrics', []):

                if metric.name + '_train' not in dataframe_dict:
                    dataframe_dict[metric.name + '_train'] = []
                dataframe_dict[metric.name + '_train'].append(train_results[metric.name][i])

                if metric.name + '_val' not in dataframe_dict:
                    dataframe_dict[metric.name + '_val'] = []
                dataframe_dict[metric.name + '_val'].append(val_results[metric.name][i])

    df = pd.DataFrame(data=dataframe_dict)

    joblib.dump(df, path_to_results)

    return df