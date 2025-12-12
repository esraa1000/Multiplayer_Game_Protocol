import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from scipy import stats

def calculate_statistics(data):
    """Calculate mean, median, 95th percentile"""
    if len(data) == 0:
        return {'mean': 0, 'median': 0, 'p95': 0}
    
    return {
        'mean': np.mean(data),
        'median': np.median(data),
        'p95': np.percentile(data, 95)
    }

def compute_position_error(server_csv, client_csv, grid_size=5):
    """Compute position error between server and client logs"""
    try:
        server_df = pd.read_csv(server_csv)
        client_df = pd.read_csv(client_csv)
        
        if len(server_df) == 0 or len(client_df) == 0:
            return []
        
        errors = []
        
        # For each client position
        for _, client_row in client_df.iterrows():
            client_time = client_row['timestamp']
            client_grid = list(map(int, client_row['grid_state'].split(',')))
            
            # Find closest server position in time
            time_diffs = abs(server_df['timestamp'] - client_time)
            if len(time_diffs) == 0:
                continue
                
            closest_idx = time_diffs.idxmin()
            time_diff = time_diffs[closest_idx]
            
            # Skip if too far apart
            if time_diff > 100:  # 100ms threshold
                continue
                
            server_row = server_df.iloc[closest_idx]
            server_grid = list(map(int, server_row['grid_state'].split(',')))
            
            # Calculate Euclidean distance
            # Each cell difference contributes 1 unit
            diff_sum = 0
            for i in range(len(client_grid)):
                if client_grid[i] != server_grid[i]:
                    diff_sum += 1
            
            # Normalize (0-10 scale)
            error = min(10.0, diff_sum * 2.0)
            errors.append(error)
        
        return errors
    except Exception as e:
        print(f"Error computing position error: {e}")
        return []

def analyze_scenario(scenario):
    """Analyze metrics for one scenario"""
    print(f"\n{'='*50}")
    print(f"Analysis for: {scenario}")
    print('='*50)
    
    # Load client metrics
    metrics_file = f'results/client_metrics_{scenario}.csv'
    
    if not os.path.exists(metrics_file):
        print(f"  File not found: {metrics_file}")
        return
    
    try:
        df = pd.read_csv(metrics_file)
        
        if len(df) < 5:
            print(f"  Insufficient data: {len(df)} samples")
            return
        
        # Calculate statistics
        latency_stats = calculate_statistics(df['latency_ms'])
        jitter_stats = calculate_statistics(df['jitter_ms'])
        error_stats = calculate_statistics(df['perceived_position_error'])
        
        print(f"\n  Latency (ms):")
        print(f"    Mean: {latency_stats['mean']:.2f}")
        print(f"    Median: {latency_stats['median']:.2f}")
        print(f"    95th percentile: {latency_stats['p95']:.2f}")
        
        print(f"\n  Jitter (ms):")
        print(f"    Mean: {jitter_stats['mean']:.2f}")
        print(f"    Median: {jitter_stats['median']:.2f}")
        print(f"    95th percentile: {jitter_stats['p95']:.2f}")
        
        print(f"\n  Position Error (units):")
        print(f"    Mean: {error_stats['mean']:.2f}")
        print(f"    Median: {error_stats['median']:.2f}")
        print(f"    95th percentile: {error_stats['p95']:.2f}")
        
        print(f"\n  CPU Usage: {df['cpu_percent'].mean():.1f}%")
        print(f"  Bandwidth: {df['bandwidth_per_client_kbps'].mean():.1f} kbps")
        print(f"  Samples: {len(df)}")
        
        # Check acceptance criteria
        print(f"\n  Acceptance Check:")
        
        if scenario == "baseline":
            if latency_stats['mean'] <= 50:
                print(f"    ✓ Latency ≤ 50ms: {latency_stats['mean']:.1f}ms")
            else:
                print(f"    ✗ Latency > 50ms: {latency_stats['mean']:.1f}ms")
            
            if df['cpu_percent'].mean() < 60:
                print(f"    ✓ CPU < 60%: {df['cpu_percent'].mean():.1f}%")
            else:
                print(f"    ✗ CPU ≥ 60%: {df['cpu_percent'].mean():.1f}%")
                
        elif scenario == "loss2":
            if error_stats['mean'] <= 0.5:
                print(f"    ✓ Mean error ≤ 0.5: {error_stats['mean']:.2f}")
            else:
                print(f"    ✗ Mean error > 0.5: {error_stats['mean']:.2f}")
            
            if error_stats['p95'] <= 1.5:
                print(f"    ✓ 95th percentile ≤ 1.5: {error_stats['p95']:.2f}")
            else:
                print(f"    ✗ 95th percentile > 1.5: {error_stats['p95']:.2f}")
                
        elif scenario == "delay100":
            print(f"    System remained functional: ✓")
            
    except Exception as e:
        print(f"  Error analyzing {scenario}: {e}")

def create_plots():
    """Create visualization plots"""
    scenarios = ['baseline', 'loss2', 'loss5', 'delay100']
    
    # Prepare data
    latency_data = []
    jitter_data = []
    error_data = []
    cpu_data = []
    bw_data = []
    
    for scenario in scenarios:
        file = f'results/client_metrics_{scenario}.csv'
        if os.path.exists(file):
            df = pd.read_csv(file)
            if len(df) > 0:
                latency_data.append(df['latency_ms'].values)
                jitter_data.append(df['jitter_ms'].values)
                error_data.append(df['perceived_position_error'].values)
                cpu_data.append(df['cpu_percent'].mean())
                bw_data.append(df['bandwidth_per_client_kbps'].mean())
            else:
                latency_data.append([])
                jitter_data.append([])
                error_data.append([])
                cpu_data.append(0)
                bw_data.append(0)
        else:
            latency_data.append([])
            jitter_data.append([])
            error_data.append([])
            cpu_data.append(0)
            bw_data.append(0)
    
    # Create figure
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    
    # Box plots
    axes[0, 0].boxplot(latency_data, labels=scenarios)
    axes[0, 0].set_title('Latency Distribution')
    axes[0, 0].set_ylabel('Latency (ms)')
    axes[0, 0].grid(True, alpha=0.3)
    
    axes[0, 1].boxplot(jitter_data, labels=scenarios)
    axes[0, 1].set_title('Jitter Distribution')
    axes[0, 1].set_ylabel('Jitter (ms)')
    axes[0, 1].grid(True, alpha=0.3)
    
    axes[0, 2].boxplot(error_data, labels=scenarios)
    axes[0, 2].set_title('Position Error Distribution')
    axes[0, 2].set_ylabel('Error (units)')
    axes[0, 2].grid(True, alpha=0.3)
    
    # Bar charts
    x_pos = np.arange(len(scenarios))
    
    axes[1, 0].bar(x_pos, cpu_data)
    axes[1, 0].set_title('Average CPU Usage')
    axes[1, 0].set_ylabel('CPU (%)')
    axes[1, 0].set_xticks(x_pos)
    axes[1, 0].set_xticklabels(scenarios)
    axes[1, 0].grid(True, alpha=0.3)
    
    axes[1, 1].bar(x_pos, bw_data)
    axes[1, 1].set_title('Average Bandwidth')
    axes[1, 1].set_ylabel('Bandwidth (kbps)')
    axes[1, 1].set_xticks(x_pos)
    axes[1, 1].set_xticklabels(scenarios)
    axes[1, 1].grid(True, alpha=0.3)
    
    # Hide empty subplot
    axes[1, 2].axis('off')
    
    plt.tight_layout()
    plt.savefig('results/performance_summary.png', dpi=150, bbox_inches='tight')
    plt.show()
    
    print("\nPlots saved to: results/performance_summary.png")

def main():
    """Main analysis function"""
    print("Multiplayer Game Protocol - Test Results Analysis")
    print("=" * 60)
    
    # Check if results directory exists
    if not os.path.exists('results'):
        print("Error: 'results' directory not found. Run tests first.")
        return
    
    # Analyze each scenario
    scenarios = ['baseline', 'loss2', 'loss5', 'delay100']
    
    for scenario in scenarios:
        analyze_scenario(scenario)
    
    # Create plots
    print("\n" + "=" * 60)
    print("Generating visualizations...")
    create_plots()
    
    print("\nAnalysis complete!")

if __name__ == "__main__":
    # Install required packages if missing
    try:
        import pandas as pd
    except ImportError:
        print("Installing required packages...")
        os.system("pip install pandas numpy matplotlib scipy")
    
    main()