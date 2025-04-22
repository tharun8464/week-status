/**
 * Team Performance Visualization
 * This script renders visualizations for the team performance data
 */

document.addEventListener('DOMContentLoaded', function() {
    // Check if the team performance chart element exists
    const teamChartElement = document.getElementById('teamPerformanceChart');
    const timeRangeSelect = document.getElementById('performanceTimeRange');
    const employeeTableBody = document.querySelector('#employeePerformanceTable tbody');
    
    if (teamChartElement && timeRangeSelect) {
        // Create chart instances
        let teamChart = null;
        
        // Function to load performance data
        const loadPerformanceData = (weeks = 8) => {
            // Show loading indicator
            teamChartElement.innerHTML = '<div class="d-flex justify-content-center align-items-center" style="height: 200px;"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div></div>';
            
            // Clear employee table
            if (employeeTableBody) {
                employeeTableBody.innerHTML = '<tr><td colspan="4" class="text-center"><div class="spinner-border spinner-border-sm text-primary me-2" role="status"></div> Loading data...</td></tr>';
            }
            
            fetch(`/admin/api/team-performance?weeks=${weeks}`)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        renderTeamChart(data);
                        populateEmployeeTable(data);
                    } else {
                        console.error("Error loading performance data:", data.error);
                        teamChartElement.innerHTML = `<div class="alert alert-danger m-3">Error loading data: ${data.error}</div>`;
                        if (employeeTableBody) {
                            employeeTableBody.innerHTML = `<tr><td colspan="4" class="text-center text-danger">Error loading data</td></tr>`;
                        }
                    }
                })
                .catch(error => {
                    console.error("Error fetching performance data:", error);
                    teamChartElement.innerHTML = `<div class="alert alert-danger m-3">Error fetching data: ${error.message}</div>`;
                    if (employeeTableBody) {
                        employeeTableBody.innerHTML = `<tr><td colspan="4" class="text-center text-danger">Error fetching data</td></tr>`;
                    }
                });
        };
        
        // Function to render team performance chart
        const renderTeamChart = (data) => {
            // Clear the canvas
            teamChartElement.innerHTML = '';
            const canvas = document.createElement('canvas');
            teamChartElement.appendChild(canvas);
            
            // Destroy previous chart if exists
            if (teamChart) {
                teamChart.destroy();
            }
            
            // Prepare data
            const labels = data.weeks;
            const onTimeData = data.team_data.map(week => week.on_time_percentage);
            const lateData = data.team_data.map(week => week.late_percentage);
            const missingData = data.team_data.map(week => week.missing_percentage);
            
            // Create stacked bar chart
            const ctx = canvas.getContext('2d');
            teamChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'On Time',
                            data: onTimeData,
                            backgroundColor: '#28a745',
                            borderColor: '#28a745',
                            borderWidth: 1
                        },
                        {
                            label: 'Late',
                            data: lateData,
                            backgroundColor: '#ffc107',
                            borderColor: '#ffc107',
                            borderWidth: 1
                        },
                        {
                            label: 'Missing',
                            data: missingData,
                            backgroundColor: '#dc3545',
                            borderColor: '#dc3545',
                            borderWidth: 1
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            stacked: true,
                            grid: {
                                color: 'rgba(255, 255, 255, 0.1)'
                            },
                            ticks: {
                                color: '#adb5bd'
                            }
                        },
                        y: {
                            stacked: true,
                            beginAtZero: true,
                            max: 100,
                            grid: {
                                color: 'rgba(255, 255, 255, 0.1)'
                            },
                            ticks: {
                                color: '#adb5bd',
                                callback: function(value) {
                                    return value + '%';
                                }
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return context.dataset.label + ': ' + Math.round(context.raw) + '%';
                                }
                            }
                        }
                    }
                }
            });
        };
        
        // Function to populate employee performance table
        const populateEmployeeTable = (data) => {
            if (!employeeTableBody) return;
            
            // Clear existing rows
            employeeTableBody.innerHTML = '';
            
            // Sort employees by on-time percentage (descending)
            const sortedEmployees = [...data.employee_data].sort((a, b) => b.on_time_percentage - a.on_time_percentage);
            
            if (sortedEmployees.length === 0) {
                employeeTableBody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">No employee data available</td></tr>';
                return;
            }
            
            // Add a row for each employee
            sortedEmployees.forEach(employee => {
                const row = document.createElement('tr');
                
                // Employee name cell
                const nameCell = document.createElement('td');
                nameCell.innerHTML = `
                    <div class="d-flex align-items-center">
                        <div class="avatar-circle me-2" style="width: 30px; height: 30px; font-size: 12px;">
                            ${employee.name.charAt(0).toUpperCase()}
                        </div>
                        <span>${employee.name}</span>
                    </div>
                `;
                
                // Performance indicators cell
                const indicatorsCell = document.createElement('td');
                indicatorsCell.className = 'text-center';
                
                const indicators = document.createElement('div');
                indicators.className = 'd-flex justify-content-center';
                
                // Create colored indicators for each week
                employee.weeks.forEach(status => {
                    let color;
                    let tooltip;
                    if (status === 2) {
                        color = 'bg-success';
                        tooltip = 'On time';
                    } else if (status === 1) {
                        color = 'bg-warning';
                        tooltip = 'Late';
                    } else {
                        color = 'bg-danger';
                        tooltip = 'Missing';
                    }
                    
                    const indicator = document.createElement('div');
                    indicator.className = `${color} mx-1`;
                    indicator.setAttribute('data-bs-toggle', 'tooltip');
                    indicator.setAttribute('title', tooltip);
                    indicator.style.width = '10px';
                    indicator.style.height = '10px';
                    indicator.style.borderRadius = '2px';
                    
                    indicators.appendChild(indicator);
                });
                
                indicatorsCell.appendChild(indicators);
                
                // On-time percentage cell
                const percentageCell = document.createElement('td');
                percentageCell.className = 'text-center';
                
                // Create progress bar
                const progressBar = document.createElement('div');
                progressBar.className = 'progress bg-dark' + (employee.on_time_percentage < 50 ? ' bg-opacity-75' : '');
                progressBar.style.height = '6px';
                
                const progressFill = document.createElement('div');
                let progressClass = 'progress-bar';
                if (employee.on_time_percentage >= 75) {
                    progressClass += ' bg-success';
                } else if (employee.on_time_percentage >= 50) {
                    progressClass += ' bg-info';
                } else if (employee.on_time_percentage >= 25) {
                    progressClass += ' bg-warning';
                } else {
                    progressClass += ' bg-danger';
                }
                
                progressFill.className = progressClass;
                progressFill.style.width = `${employee.on_time_percentage}%`;
                progressFill.setAttribute('aria-valuenow', employee.on_time_percentage);
                progressFill.setAttribute('aria-valuemin', '0');
                progressFill.setAttribute('aria-valuemax', '100');
                
                progressBar.appendChild(progressFill);
                
                // Add percentage text and progress bar
                const percentageWrap = document.createElement('div');
                percentageWrap.className = 'd-flex flex-column';
                
                const percentageText = document.createElement('small');
                percentageText.textContent = `${employee.on_time_percentage}%`;
                percentageText.className = 'mb-1';
                
                percentageWrap.appendChild(percentageText);
                percentageWrap.appendChild(progressBar);
                
                percentageCell.appendChild(percentageWrap);
                
                // Trend cell
                const trendCell = document.createElement('td');
                trendCell.className = 'text-center';
                
                let trendIcon, trendColor;
                if (employee.trend === 'up') {
                    trendIcon = 'fa-arrow-up';
                    trendColor = 'text-success';
                } else if (employee.trend === 'down') {
                    trendIcon = 'fa-arrow-down';
                    trendColor = 'text-danger';
                } else {
                    trendIcon = 'fa-minus';
                    trendColor = 'text-secondary';
                }
                
                trendCell.innerHTML = `<i class="fas ${trendIcon} ${trendColor}"></i>`;
                
                // Add cells to row
                row.appendChild(nameCell);
                row.appendChild(indicatorsCell);
                row.appendChild(percentageCell);
                row.appendChild(trendCell);
                
                // Add row to table
                employeeTableBody.appendChild(row);
            });
            
            // Initialize tooltips for the indicators
            var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
            tooltipTriggerList.map(function (tooltipTriggerEl) {
                return new bootstrap.Tooltip(tooltipTriggerEl);
            });
        };
        
        // Handle time range changes
        if (timeRangeSelect) {
            timeRangeSelect.addEventListener('change', function() {
                const weeks = parseInt(this.value);
                loadPerformanceData(weeks);
            });
        }
        
        // Initial load of performance data
        loadPerformanceData(8);
    }
});