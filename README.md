# cflib for esp-drone

[cflib](./ORIGIN.md) is an API written in Python that is used to communicate with the Crazyflie
and Crazyflie 2.0 quadcopters.

In this fork, the cflib is used to communicate with the [esp-drone](https://github.com/espressif/esp-drone) through the WiFi connection and UDP protocol.

## Using the modified cflib for esp-drone

To install the modified cflib for esp-drone, you can follow the instructions below.

```bash
  pip install git+https://github.com/leeebo/crazyflie-lib-python.git
```
## Using the GUI tools for esp-drone

The folked version of the [cfclient](https://github.com/leeebo/crazyflie-clients-python) can be used to communicate with the esp-drone.

## Development

If you want to develop features or fix bugs in the cflib, you can follow the instructions below.

* [Fork the cflib](https://help.github.com/articles/fork-a-repo/), [click](https://github.com/leeebo/crazyflie-lib-python/fork) to fork
* [Clone the cflib](https://help.github.com/articles/cloning-a-repository/) please replace `leeebo` with your GitHub username.

```bash
  git clone https://github.com/leeebo/crazyflie-lib-python.git
```

* [Install the cflib in editable mode](http://pip-python3.readthedocs.org/en/latest/reference/pip_install.html?highlight=editable#editable-installs)

```bash
  pip install -e path/to/cflib
```

