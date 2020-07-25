# Maintenance


## Symptoms

- `test_gomus_version` failed

  See [Update gomus version](#update-gomus-version).

- `test_session_id_is_valid` failed

  tbd


## Tasks

### Update project dependencies

#### Motivation

Nearly all project dependencies are specified by using a fixed version.
This protects our solution against breaking changes from any package updates.
However, updating packages, in general, is a good idea, because relying on old packages
a) impedes further development as new features in libraries cannot be used,
b) can break the connection to external access points whose interface has changed, and
c) may leave recently discovered security leaks unfixed.
Thus, updates should be carried out on a regular schedule.

#### Update python (pip) dependencies

1. Check out a new branch.
2. Connect to the docker (`make connect`), and run `make upgrade-requirements`.
3. If `pip check` fails, you need to manually add the required dependencies to `docker/requirements.txt`.
   This is necessary because of https://github.com/pypa/pip/issues/988.

   **Remark:** You may need to "touch" the Dockerfile manually by editing it's first line in order to make sure that the previous docker cache is not reused, which would lead to the changes in `requirements.txt` are not checked at all!

4. Create a merge request with your changes and make sure the CI passes.
5. Once it passes, merge the branch.

#### Update docker images

Each used docker image is specified either in `docker/docker-compose.yml` or in the linked Dockerfile.
For more information about the docker containers, please refer to the [documentation](DOCUMENTATION.md#docker-containers).

1. To update a docker image, edit the `image` key in the yaml file respectively the `FROM` command in the Dockerfile.
   Be careful to watch for any breaking changes in the updates.
2. Restart the container by running `make shutdown-<docker> startup-<docker>`.

### Update gomus version

#### Motivation

From time to time, Giant Monkey uses to publish a new version of go~mus.
As we are scraping certain contents from the gomus web interface, each of these changes can possibly break our gomus tasks.
The `TestGomusVersion` assertions will report any version change.

#### Action

1. Check out the [gomus changelog](https://barberini.gomus.de/wiki/spaces/REL/pages/1787854853) (barberini.gomus.de > Helpdesk > Changelog) and search for possible breaking changes (for example, the layout of the customer data could have changed).
2. Make sure all other gomus tests pass.
3. If there are any breaking changes, the gomus tasks need to be updated.
4. Go to `tests/gomus/test_gomus_version.py` and update the `EXPECTED_VERSION_TAG` constant to match the new version name.

#### Remarks

- In the past, we have experienced a few changes in the gomus HTML format without the version number being incremented.
  In this case, the `test_gomus_version` scraper needs to be updated. See !169.
