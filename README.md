# Awesome Barberini Tools

## About

Data Analytics tool to create an awesome dashboard for the Museum Barberini, Potsdam, to help them analyze and assess customer, advertising, and social media data!  

## Installation

See `INSTALLATION.md`.

## Documentation

tbc 🙂

## Usage

### Controlling the pipeline

#### Open the luigi webinterface

```bash
 make docker-do do='make luigi-scheduler'
```

This will also start a webserver on http://localhost:8082 where you can trace all running tasks.

#### Running the pipeline manually

```bash
 make docker-do do='make luigi'
```

#### Accessing the docker containers

Have a look at our beautiful `Makefile`! To access the luigi docker, do:

```bash
make startup connect
```

Close the session by executing:

```bash
make shutdown
```

## Credits

**Authors:** Laura Holz, Selina Reinhard, Leon Schmidt, Georg Tennigkeit, Christoph Thiede, Tom Wollnik (bachelor project BPFN1 @ HPI).  
**Organizations:** [Hasso Plattner Institute, Potsdam](https://hpi.de/en); [Museum Barberini](https://www.museum-barberini.com/en/); Hasso Plattner Foundation.  
