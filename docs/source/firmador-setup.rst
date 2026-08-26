Firmador (digital signature) local setup
===========================================

The ``firmador_digital`` module (``djgentelella[firmador]``) talks to a
**Firmador Libre** server. There is no published image for it; you build one
locally from two upstream repos before ``make services-sign`` has anything to
run.

Step 1: build the Firmador Libre core
-----------------------------------------

.. code:: bash

    git clone https://codeberg.org/firmador/firmador.git
    cd firmador
    mvn clean install

This installs the core library into your local Maven repository (``~/.m2``);
the API build below depends on it being there.

Step 2: build the Firmador API image
-----------------------------------------

.. code:: bash

    git clone https://codeberg.org/firmador/firmador_api.git
    cd firmador_api
    make build

This produces the ``firmadorlibreserver`` image that
``scripts/run_services.sh --sign`` (or ``make services-sign``) runs on
``localhost:9001``.

Desktop signing agent
-----------------------------------------

Signing itself happens in the user's browser through a local agent, not on
the server -- download it from
`firmador.libre.cr/descargar.html <https://firmador.libre.cr/descargar.html>`_.

First run, one-time setup:

1. Open the app and switch out of simplified mode ("modo no simplificado").
2. Go to the **Conexión** tab and select **firmador remoto** ("connect").
3. It will ask for permission to add the app running on the demo's port
   (``127.0.0.1:8000``, or wherever it runs) -- accept it. Without this the
   agent refuses connections from that origin and signing fails silently.

Running it
-----------------------------------------

.. code:: bash

    make services-sign

Stop with Ctrl+C; both MailHog and Firmador are removed on exit.
