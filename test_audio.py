from network.audio_receiver import AudioReceiver

receiver = AudioReceiver("10.228.129.125", 8081)

try:
    receiver.connect()
    input("Press Enter to stop...")
finally:
    receiver.close()