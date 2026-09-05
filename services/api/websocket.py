from fastapi import WebSocket, WebSocketDisconnect

from services.event_bus.bus import event_bus


async def friday_websocket(websocket: WebSocket):

    print("[FRIDAY WS] Client connecting...")

    await websocket.accept()

    print("[FRIDAY WS] Client connected")

    queue = event_bus.subscribe()

    try:

        while True:

            event = await queue.get()

            print(
                f"[FRIDAY WS] Sending event: "
                f"{event.type} - {event.title}"
            )

            await websocket.send_json(
                event.model_dump(mode="json")
            )

    except WebSocketDisconnect:

        print(
            "[FRIDAY WS] Client disconnected"
        )

    except Exception as error:

        print(
            f"[FRIDAY WS] Error: {error}"
        )

    finally:

        event_bus.unsubscribe(queue)

        print(
            "[FRIDAY WS] Subscriber removed"
        )