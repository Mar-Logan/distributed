# DistRes: Distributed Resource Access and Synchronisation Engine

DistRes is the distributed upgrade of the original ConRes coursework project. ConRes was a local Flask-based concurrency system that allowed multiple users to log in, wait for access, and safely read or edit a shared product specification file. DistRes keeps that same core idea, but moves the important coordination into a TCP client-server system.

The main goal is simple: several users can connect from different client nodes, ask to access shared resources, and the server keeps the resource state safe and consistent.

## From ConRes to DistRes

ConRes handled concurrency inside one local Flask application. The Flask app directly managed users, sessions, semaphores, locks, the SQLite database, and `ProductSpecification.txt`.

DistRes changes this architecture. The TCP server is now the authoritative owner of the shared resources. Clients do not directly open the database or the file. They send structured JSON messages to the server, and the server decides what is allowed.

In short:

- ConRes: local web app with local concurrency control.
- DistRes: distributed client-server system with server-side coordination.
- The existing web pages are still used, but Flask now acts as a web-to-TCP client adapter.
- A terminal client is also available and uses the same TCP protocol.

## High-Level Architecture

![High-level DistRes architecture](docs/images/high-level-architecture.png)

The diagram above shows the system at a simple block level. Web clients and terminal clients both connect to the DistRes TCP server. The server contains the two key requirement areas:

- Concurrent Users Manager: controls active and waiting users.
- Control Access Manager: controls safe read/write access to the shared resource.

The server also owns the credential database, shared product specification resource, file access queue, readers-writer lock, session/semaphore state, and publish-subscribe notification system.

## UML Deployment View

![DistRes UML deployment diagram](docs/images/deployment-diagram.png)

The deployment view shows DistRes running as a distributed system. Client nodes communicate over TCP sockets with the server node. The server hosts the database, shared file, service logic, locking, queue management, and publish-subscribe notifier.

This demonstrates that the clients are separate from the authoritative resource owner. They coordinate through network messages instead of shared memory.

## UML Component View

![DistRes UML component diagram](docs/images/component-diagram.png)

The component view shows the layered structure of the system:

- Client Layer: browser client and terminal client.
- Communication Layer: web adapter, CLI proxy, and TCP server connection.
- Service Layer: request routing, authentication, resource management, queueing, and publish-subscribe.
- Data and Concurrency Layer: credential data, shared file resource, session state, and readers-writer lock.

This structure keeps responsibilities separated and makes the distributed design easier to explain, test, and extend.

## Main Features

- TCP socket server using Python sockets.
- One server thread per connected client.
- JSON newline-delimited message protocol.
- Web client interface through Flask.
- Terminal menu client.
- Server-side SQLite credential checking.
- Server-side session management.
- Semaphore-based active and waiting user control.
- Concurrent read access to `ProductSpecification.txt`.
- Exclusive write access for one writer at a time.
- Fair file access queue for queued writers.
- Publish-subscribe notifications after successful writes.
- Cleanup on logout or unexpected disconnect.

## How The Web Integration Works

The browser still uses normal Flask routes such as login, dashboard, read document, and edit document. However, Flask no longer controls the shared resources directly.

The flow is:

```text
Browser
  -> Flask Web Adapter
  -> DistRes TCP Server
  -> Server-owned database, file, sessions, locks, and queues
```

For example:

- Login sends `login_request`.
- Reading sends `read_file_request`.
- Editing sends `write_file_request`.
- Saving sends `write_file_commit`.
- Dashboard polling sends `system_state_request`.
- Update notifications are received through `resource_updated`.

## Folder Structure

```text
distributed/
  app.py                         Flask web frontend adapter
  run_server.py                  Starts the DistRes TCP server
  ProductSpecification.txt       Server-owned shared file
  users.db                       Server-owned credential database

  client/
    communication/               Terminal client proxy methods
    core/                        Client connection and receive handling
    ui/                          Terminal menu interface

  server/
    server.py                    TCP server socket accept loop
    client_handler.py            One handler thread per client
    router.py                    Routes message types to server actions
    connection_manager.py        Tracks connected clients and sends messages
    core/                        Locks, queues, sessions, semaphores
    data/                        SQLite access and authentication
    services/                    Main DistRes application logic

  shared/
    protocol.py                  JSON message helpers
    logger.py                    Shared logging setup

  web/
    web_distres_client.py        Flask-to-TCP client adapter
    web_client_registry.py       Stores TCP clients for browser sessions
```

## How To Run

First start the TCP server:

```powershell
cd C:\Users\lmart\Documents\distributed
python run_server.py
```

Then start the Flask web frontend:

```powershell
cd C:\Users\lmart\Documents\distributed
python app.py
```

Open the web app:

```text
http://127.0.0.1:5000
```

Optional terminal client:

```powershell
cd C:\Users\lmart\Documents\distributed
python -m client.main
```

## Sample Users

The sample database uses user ID and username:

```text
1001 / alice
1002 / bob
1003 / charlie
1004 / diana
1005 / eve
1006 / frank
```

## Demonstration Scenario

1. Start `run_server.py`.
2. Start `app.py`.
3. Log in as Alice in one browser.
4. Log in as Diana in another browser or private window.
5. Alice opens the shared document in read mode.
6. Diana tries to edit the document and is queued.
7. Alice returns to the dashboard, releasing read mode.
8. Diana is automatically granted write access and redirected to the editor.
9. Diana saves a change.
10. Alice receives a resource update notification.

This demonstrates client-server coordination, concurrent reading, exclusive writing, fair queueing, and publish-subscribe notifications.

## Notes About The Images

Save the three supplied diagrams into this folder:

```text
docs/images/
```

Use these filenames so the README image links render correctly:

```text
high-level-architecture.png
deployment-diagram.png
component-diagram.png
```

The diagrams are intentionally design-level. They describe the system structure and deployment without focusing too much on low-level implementation files.
