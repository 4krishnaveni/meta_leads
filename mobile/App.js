import React, { useEffect, useRef, useState } from 'react';
import { SafeAreaView, FlatList, Text, View, StyleSheet, StatusBar } from 'react-native';

const BACKEND_HOST = 'fdbd141p-8000.inc1.devtunnels.ms'; // <- your ngrok host, no https://
const WS_URL = `wss://${BACKEND_HOST}/ws`;

export default function App() {
    const [leads, setLeads] = useState([]);
    const [connected, setConnected] = useState(false);
    const wsRef = useRef(null);
    const retryRef = useRef(null);

    useEffect(() => {
        let closedByUs = false;

        const connect = () => {
            const ws = new WebSocket(WS_URL);
            wsRef.current = ws;

            ws.onopen = () => setConnected(true);

            ws.onmessage = (event) => {
                const msg = JSON.parse(event.data);
                if (msg.type === 'snapshot') {
                    setLeads(msg.leads);
                } else if (msg.type === 'new_lead') {
                    setLeads((prev) =>
                        prev.some((l) => l.id === msg.lead.id) ? prev : [msg.lead, ...prev]
                    );
                }
            };

            ws.onclose = () => {
                setConnected(false);
                if (!closedByUs) retryRef.current = setTimeout(connect, 2000); // auto-reconnect
            };

            ws.onerror = () => ws.close();
        };

        connect();
        return () => {
            closedByUs = true;
            clearTimeout(retryRef.current);
            wsRef.current && wsRef.current.close();
        };
    }, []);

    const renderItem = ({ item }) => (
        <View style={styles.card}>
            <Text style={styles.name}>{item.fields.full_name || item.fields.first_name || 'Unknown'}</Text>
            <Text style={styles.line}>{item.fields.email || '-'}</Text>
            <Text style={styles.line}>{item.fields.phone_number || '-'}</Text>
            <Text style={styles.meta}>{item.created_time}</Text>
        </View>
    );

    return (
        <SafeAreaView style={styles.container}>
            <View style={styles.header}>
                <Text style={styles.title}>Leads ({leads.length})</Text>
                <Text style={{ color: connected ? 'green' : 'red' }}>
                    {connected ? '● Live' : '● Reconnecting...'}
                </Text>
            </View>
            <FlatList
                data={leads}
                keyExtractor={(item) => item.id}
                renderItem={renderItem}
                ListEmptyComponent={<Text style={styles.empty}>Waiting for leads...</Text>}
            />
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    container: { flex: 1, backgroundColor: '#f4f5f7', paddingTop: StatusBar.currentHeight || 0 },
    header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 16 },
    title: { fontSize: 22, fontWeight: '700' },
    card: { backgroundColor: '#fff', marginHorizontal: 16, marginBottom: 10, padding: 14, borderRadius: 10, elevation: 2 },
    name: { fontSize: 17, fontWeight: '600', marginBottom: 4 },
    line: { fontSize: 14, color: '#333' },
    meta: { fontSize: 12, color: '#888', marginTop: 6 },
    empty: { textAlign: 'center', marginTop: 40, color: '#888' },
});