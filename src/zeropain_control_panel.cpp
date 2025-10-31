/*
 * zeropain_control_panel.cpp - ZeroPain Therapeutics Laboratory Control System
 * Dark-themed professional interface with mercury arc rectifier visualization
 * 
 * Compile with native optimizations:
 * g++ -std=c++17 -O3 -march=native -mtune=native -flto -ffast-math \
 *     zeropain_control_panel.cpp -lGL -lglfw -lGLEW -lImGui -lImPlot \
 *     -pthread -fopenmp -lm -o zeropain_control
 * 
 * Or use the build script: ./build_control_panel.sh
 */

#include <iostream>
#include <vector>
#include <deque>
#include <map>
#include <string>
#include <cstring>
#include <memory>
#include <thread>
#include <atomic>
#include <mutex>
#include <chrono>
#include <iomanip>
#include <sstream>
#include <algorithm>
#include <cmath>
#include <fstream>
#include <random>

// OpenGL and Window Management
#include <GL/glew.h>
#include <GLFW/glfw3.h>

// ImGui
#include "imgui.h"
#include "imgui_impl_glfw.h"
#include "imgui_impl_opengl3.h"
#include "implot.h"

// Include C simulation headers
extern "C" {
    #include "patient_sim.h"
}

// ============================================================================
// LABORATORY THEME CONFIGURATION
// ============================================================================

namespace LabTheme {
    // Color scheme inspired by vintage laboratory equipment
    const ImVec4 BACKGROUND = ImVec4(0.08f, 0.08f, 0.10f, 1.0f);  // Deep charcoal
    const ImVec4 PANEL_BG = ImVec4(0.12f, 0.12f, 0.14f, 0.95f);   // Dark panel
    const ImVec4 HEADER_BG = ImVec4(0.18f, 0.20f, 0.22f, 1.0f);   // Header gray
    const ImVec4 MERCURY_BLUE = ImVec4(0.2f, 0.6f, 1.0f, 1.0f);   // Arc blue
    const ImVec4 MERCURY_GLOW = ImVec4(0.4f, 0.7f, 1.0f, 0.6f);   // Glow effect
    const ImVec4 WARNING_AMBER = ImVec4(1.0f, 0.7f, 0.0f, 1.0f);  // Warning
    const ImVec4 SUCCESS_GREEN = ImVec4(0.0f, 0.9f, 0.3f, 1.0f);  // Success
    const ImVec4 DANGER_RED = ImVec4(1.0f, 0.2f, 0.2f, 1.0f);     // Danger
    const ImVec4 TEXT_DIM = ImVec4(0.6f, 0.6f, 0.65f, 1.0f);      // Dim text
    const ImVec4 TEXT_BRIGHT = ImVec4(0.9f, 0.9f, 0.95f, 1.0f);   // Bright text
    
    void ApplyTheme() {
        ImGuiStyle& style = ImGui::GetStyle();
        
        // Main styling
        style.WindowRounding = 2.0f;
        style.FrameRounding = 2.0f;
        style.ScrollbarRounding = 2.0f;
        style.GrabRounding = 2.0f;
        style.TabRounding = 2.0f;
        style.WindowBorderSize = 1.0f;
        style.FrameBorderSize = 1.0f;
        style.PopupBorderSize = 1.0f;
        style.ItemSpacing = ImVec2(8, 6);
        style.ItemInnerSpacing = ImVec2(6, 4);
        style.IndentSpacing = 20.0f;
        style.ScrollbarSize = 14.0f;
        style.GrabMinSize = 12.0f;
        
        // Colors
        ImVec4* colors = style.Colors;
        colors[ImGuiCol_WindowBg] = PANEL_BG;
        colors[ImGuiCol_Border] = ImVec4(0.28f, 0.28f, 0.30f, 0.8f);
        colors[ImGuiCol_FrameBg] = ImVec4(0.16f, 0.16f, 0.18f, 1.0f);
        colors[ImGuiCol_FrameBgHovered] = ImVec4(0.20f, 0.22f, 0.24f, 1.0f);
        colors[ImGuiCol_FrameBgActive] = ImVec4(0.24f, 0.26f, 0.28f, 1.0f);
        colors[ImGuiCol_TitleBg] = HEADER_BG;
        colors[ImGuiCol_TitleBgActive] = ImVec4(0.20f, 0.22f, 0.24f, 1.0f);
        colors[ImGuiCol_MenuBarBg] = ImVec4(0.14f, 0.14f, 0.16f, 1.0f);
        colors[ImGuiCol_ScrollbarBg] = ImVec4(0.10f, 0.10f, 0.12f, 0.8f);
        colors[ImGuiCol_ScrollbarGrab] = ImVec4(0.30f, 0.30f, 0.32f, 0.8f);
        colors[ImGuiCol_CheckMark] = MERCURY_BLUE;
        colors[ImGuiCol_SliderGrab] = MERCURY_BLUE;
        colors[ImGuiCol_SliderGrabActive] = MERCURY_GLOW;
        colors[ImGuiCol_Button] = ImVec4(0.20f, 0.22f, 0.24f, 1.0f);
        colors[ImGuiCol_ButtonHovered] = ImVec4(0.28f, 0.30f, 0.32f, 1.0f);
        colors[ImGuiCol_ButtonActive] = MERCURY_BLUE;
        colors[ImGuiCol_Header] = ImVec4(0.22f, 0.24f, 0.26f, 1.0f);
        colors[ImGuiCol_HeaderHovered] = ImVec4(0.26f, 0.28f, 0.30f, 1.0f);
        colors[ImGuiCol_HeaderActive] = MERCURY_BLUE;
        colors[ImGuiCol_Tab] = ImVec4(0.18f, 0.20f, 0.22f, 1.0f);
        colors[ImGuiCol_TabHovered] = ImVec4(0.38f, 0.40f, 0.42f, 1.0f);
        colors[ImGuiCol_TabActive] = MERCURY_BLUE;
        colors[ImGuiCol_Text] = TEXT_BRIGHT;
        colors[ImGuiCol_TextDisabled] = TEXT_DIM;
        colors[ImGuiCol_PlotLines] = MERCURY_BLUE;
        colors[ImGuiCol_PlotHistogram] = MERCURY_BLUE;
    }
}

// ============================================================================
// MERCURY ARC RECTIFIER VISUALIZATION
// ============================================================================

class MercuryArcRectifier {
private:
    float intensity_ = 0.0f;
    float target_intensity_ = 0.0f;
    float glow_phase_ = 0.0f;
    float arc_flicker_ = 0.0f;
    std::chrono::steady_clock::time_point last_update_;
    
public:
    MercuryArcRectifier() : last_update_(std::chrono::steady_clock::now()) {}
    
    void SetIntensity(float intensity) {
        target_intensity_ = std::clamp(intensity, 0.0f, 1.0f);
    }
    
    void Update() {
        auto now = std::chrono::steady_clock::now();
        float dt = std::chrono::duration<float>(now - last_update_).count();
        last_update_ = now;
        
        // Smooth intensity transitions
        intensity_ = intensity_ * 0.9f + target_intensity_ * 0.1f;
        
        // Glow pulsing
        glow_phase_ += dt * 2.0f;
        if (glow_phase_ > 2 * M_PI) glow_phase_ -= 2 * M_PI;
        
        // Arc flicker simulation
        if (intensity_ > 0.1f) {
            arc_flicker_ = 0.95f + 0.05f * sin(glow_phase_ * 10.0f) + 
                          0.02f * sin(glow_phase_ * 37.0f);
        } else {
            arc_flicker_ = 0.0f;
        }
    }
    
    void Draw(const char* label, ImVec2 size = ImVec2(80, 160)) {
        Update();
        
        ImDrawList* draw_list = ImGui::GetWindowDrawList();
        ImVec2 pos = ImGui::GetCursorScreenPos();
        
        // Tube outline
        draw_list->AddRectFilled(pos, ImVec2(pos.x + size.x, pos.y + size.y),
                                 IM_COL32(20, 20, 25, 255), 4.0f);
        draw_list->AddRect(pos, ImVec2(pos.x + size.x, pos.y + size.y),
                          IM_COL32(60, 60, 70, 255), 4.0f, 0, 2.0f);
        
        // Glass tube effect
        draw_list->AddRectFilled(ImVec2(pos.x + 5, pos.y + 5),
                                 ImVec2(pos.x + size.x - 5, pos.y + size.y - 5),
                                 IM_COL32(15, 15, 20, 200), 3.0f);
        
        if (intensity_ > 0.01f) {
            // Mercury pool at bottom
            float pool_height = 20.0f;
            ImVec2 pool_pos(pos.x + 10, pos.y + size.y - pool_height - 10);
            draw_list->AddRectFilled(pool_pos,
                                     ImVec2(pos.x + size.x - 10, pos.y + size.y - 10),
                                     IM_COL32(150, 150, 160, 200), 2.0f);
            
            // Arc effect
            float arc_intensity = intensity_ * arc_flicker_;
            
            // Main arc column
            float arc_width = 20.0f + 10.0f * arc_intensity;
            float arc_x = pos.x + size.x/2;
            float arc_top = pos.y + 20;
            float arc_bottom = pos.y + size.y - pool_height - 10;
            
            // Glow layers (outer to inner)
            for (int i = 3; i >= 0; i--) {
                float layer_intensity = arc_intensity * (1.0f - i * 0.2f);
                float layer_width = arc_width * (1.5f - i * 0.3f);
                int alpha = (int)(layer_intensity * (60 + i * 40));
                
                draw_list->AddLine(ImVec2(arc_x, arc_top),
                                  ImVec2(arc_x, arc_bottom),
                                  IM_COL32(100, 180, 255, alpha),
                                  layer_width);
            }
            
            // Core arc (brightest)
            draw_list->AddLine(ImVec2(arc_x, arc_top),
                              ImVec2(arc_x, arc_bottom),
                              IM_COL32(200, 220, 255, (int)(arc_intensity * 255)),
                              arc_width * 0.3f);
            
            // Electrode glow at top
            draw_list->AddCircleFilled(ImVec2(arc_x, arc_top),
                                       8.0f + 4.0f * arc_intensity,
                                       IM_COL32(180, 200, 255, (int)(arc_intensity * 200)));
            
            // Random spark effects
            if (arc_intensity > 0.5f && (rand() % 100) < 5) {
                float spark_x = arc_x + (rand() % 20 - 10);
                float spark_y = arc_top + (rand() % (int)(arc_bottom - arc_top));
                draw_list->AddCircleFilled(ImVec2(spark_x, spark_y),
                                          2.0f, IM_COL32(255, 255, 255, 200));
            }
        }
        
        // Label
        ImGui::SetCursorScreenPos(ImVec2(pos.x, pos.y + size.y + 5));
        ImGui::TextColored(LabTheme::TEXT_DIM, "%s", label);
        ImGui::SetCursorScreenPos(ImVec2(pos.x, pos.y + size.y + 20));
        ImGui::TextColored(intensity_ > 0.5f ? LabTheme::MERCURY_BLUE : LabTheme::TEXT_DIM,
                          "%.0f%%", intensity_ * 100);
        
        // Make space for next element
        ImGui::Dummy(ImVec2(size.x, size.y + 35));
    }
};

// ============================================================================
// COMPOUND MANAGEMENT SYSTEM
// ============================================================================

class CompoundManager {
public:
    struct CompoundData {
        char name[64];
        float ki_orthosteric;
        float ki_allosteric1;
        float ki_allosteric2;
        float g_protein_bias;
        float beta_arrestin_bias;
        float t_half;
        float bioavailability;
        float intrinsic_activity;
        float tolerance_rate;
        bool prevents_withdrawal;
        bool reverses_tolerance;
        
        // Calculated metrics
        float safety_score;
        float bias_ratio;
        ImVec4 safety_color;
        
        void CalculateMetrics() {
            bias_ratio = g_protein_bias / (beta_arrestin_bias + 0.001f);
            
            // Safety scoring
            safety_score = 100.0f;
            if (intrinsic_activity > 0.7f && g_protein_bias < 5.0f) safety_score -= 20;
            if (beta_arrestin_bias > 0.5f) safety_score -= 30;
            if (g_protein_bias > 10.0f) safety_score += 10;
            if (tolerance_rate < 0.2f) safety_score += 10;
            if (reverses_tolerance) safety_score += 20;
            if (bioavailability < 0.3f) safety_score -= 10;
            if (t_half < 2.0f) safety_score -= 10;
            safety_score = std::clamp(safety_score, 0.0f, 100.0f);
            
            // Color coding
            if (safety_score > 80) safety_color = LabTheme::SUCCESS_GREEN;
            else if (safety_score > 60) safety_color = LabTheme::WARNING_AMBER;
            else safety_color = LabTheme::DANGER_RED;
        }
    };
    
    std::vector<CompoundData> compounds;
    int selected_compound = 0;
    
    CompoundManager() {
        LoadPresets();
    }
    
    void LoadPresets() {
        // SR-17018
        CompoundData sr17018;
        strcpy(sr17018.name, "SR-17018");
        sr17018.ki_orthosteric = 0;  // INFINITY
        sr17018.ki_allosteric1 = 26;
        sr17018.ki_allosteric2 = 100;
        sr17018.g_protein_bias = 8.2f;
        sr17018.beta_arrestin_bias = 0.01f;
        sr17018.t_half = 7.0f;
        sr17018.bioavailability = 0.7f;
        sr17018.intrinsic_activity = 0.38f;
        sr17018.tolerance_rate = 0.0f;
        sr17018.prevents_withdrawal = true;
        sr17018.reverses_tolerance = true;
        sr17018.CalculateMetrics();
        compounds.push_back(sr17018);
        
        // SR-14968
        CompoundData sr14968;
        strcpy(sr14968.name, "SR-14968");
        sr14968.ki_orthosteric = 0;
        sr14968.ki_allosteric1 = 10;
        sr14968.ki_allosteric2 = 50;
        sr14968.g_protein_bias = 10.0f;
        sr14968.beta_arrestin_bias = 0.1f;
        sr14968.t_half = 12.0f;
        sr14968.bioavailability = 0.6f;
        sr14968.intrinsic_activity = 1.0f;
        sr14968.tolerance_rate = 0.8f;
        sr14968.prevents_withdrawal = false;
        sr14968.reverses_tolerance = false;
        sr14968.CalculateMetrics();
        compounds.push_back(sr14968);
        
        // Buprenorphine
        CompoundData bup;
        strcpy(bup.name, "Buprenorphine");
        bup.ki_orthosteric = 0.2f;
        bup.ki_allosteric1 = 0;
        bup.ki_allosteric2 = 0;
        bup.g_protein_bias = 1.5f;
        bup.beta_arrestin_bias = 0.8f;
        bup.t_half = 37.0f;
        bup.bioavailability = 0.15f;
        bup.intrinsic_activity = 0.3f;
        bup.tolerance_rate = 0.1f;
        bup.prevents_withdrawal = true;
        bup.reverses_tolerance = false;
        bup.CalculateMetrics();
        compounds.push_back(bup);
    }
};

// ============================================================================
// SIMULATION MONITOR
// ============================================================================

class SimulationMonitor {
public:
    struct LiveMetrics {
        std::deque<float> analgesia_history;
        std::deque<float> tolerance_history;
        std::deque<float> addiction_history;
        std::deque<float> success_rate_history;
        
        float current_analgesia = 0;
        float current_tolerance = 0;
        float current_addiction = 0;
        float current_success = 0;
        
        int patients_processed = 0;
        int total_patients = 100000;
        
        void AddDataPoint(float analgesia, float tolerance, float addiction, float success) {
            const size_t max_history = 100;
            
            analgesia_history.push_back(analgesia);
            if (analgesia_history.size() > max_history) analgesia_history.pop_front();
            
            tolerance_history.push_back(tolerance);
            if (tolerance_history.size() > max_history) tolerance_history.pop_front();
            
            addiction_history.push_back(addiction);
            if (addiction_history.size() > max_history) addiction_history.pop_front();
            
            success_rate_history.push_back(success);
            if (success_rate_history.size() > max_history) success_rate_history.pop_front();
            
            current_analgesia = analgesia;
            current_tolerance = tolerance;
            current_addiction = addiction;
            current_success = success;
        }
    };
    
    LiveMetrics metrics;
    std::atomic<bool> simulation_running{false};
    std::thread simulation_thread;
    std::mutex metrics_mutex;
    MercuryArcRectifier arc_rectifier;
    
    void StartSimulation(const Protocol& protocol) {
        if (simulation_running) return;
        
        simulation_running = true;
        simulation_thread = std::thread([this, protocol]() {
            RunSimulation(protocol);
        });
        simulation_thread.detach();
    }
    
    void StopSimulation() {
        simulation_running = false;
    }
    
private:
    void RunSimulation(const Protocol& protocol) {
        // Simplified simulation for demo
        std::random_device rd;
        std::mt19937 gen(rd());
        std::normal_distribution<> analgesia_dist(0.7, 0.1);
        std::normal_distribution<> tolerance_dist(0.05, 0.02);
        std::normal_distribution<> addiction_dist(0.03, 0.01);
        
        while (simulation_running && metrics.patients_processed < metrics.total_patients) {
            // Simulate batch
            float batch_analgesia = std::clamp(analgesia_dist(gen), 0.0, 1.0);
            float batch_tolerance = std::clamp(tolerance_dist(gen), 0.0, 1.0);
            float batch_addiction = std::clamp(addiction_dist(gen), 0.0, 1.0);
            float batch_success = 0.7f + (batch_analgesia - 0.7f) * 2.0f - batch_tolerance - batch_addiction;
            batch_success = std::clamp(batch_success, 0.0, 1.0);
            
            {
                std::lock_guard<std::mutex> lock(metrics_mutex);
                metrics.AddDataPoint(batch_analgesia, batch_tolerance, batch_addiction, batch_success);
                metrics.patients_processed += 100;
            }
            
            std::this_thread::sleep_for(std::chrono::milliseconds(50));
        }
        
        simulation_running = false;
    }
};

// ============================================================================
// MAIN CONTROL PANEL APPLICATION
// ============================================================================

class ZeroPainControlPanel {
private:
    GLFWwindow* window;
    CompoundManager compound_manager;
    SimulationMonitor sim_monitor;
    Protocol current_protocol = {16.17f, 25.31f, 5.07f};
    
    // UI State
    bool show_compound_editor = true;
    bool show_simulation_control = true;
    bool show_live_metrics = true;
    bool show_protocol_designer = false;
    bool show_population_stats = false;
    bool show_safety_analysis = false;
    
    // Expanded sections
    bool expand_binding_params = true;
    bool expand_signaling_params = true;
    bool expand_pk_params = true;
    bool expand_special_props = true;
    
public:
    bool Init() {
        // Initialize GLFW
        if (!glfwInit()) {
            std::cerr << "Failed to initialize GLFW\n";
            return false;
        }
        
        // OpenGL version
        glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3);
        glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 3);
        glfwWindowHint(GLFW_OPENGL_PROFILE, GLFW_OPENGL_CORE_PROFILE);
        
        // Create window
        window = glfwCreateWindow(1920, 1080, 
            "ZeroPain Therapeutics - Laboratory Control System", nullptr, nullptr);
        if (!window) {
            std::cerr << "Failed to create window\n";
            glfwTerminate();
            return false;
        }
        
        glfwMakeContextCurrent(window);
        glfwSwapInterval(1); // VSync
        
        // Initialize GLEW
        if (glewInit() != GLEW_OK) {
            std::cerr << "Failed to initialize GLEW\n";
            return false;
        }
        
        // Setup ImGui
        IMGUI_CHECKVERSION();
        ImGui::CreateContext();
        ImPlot::CreateContext();
        
        ImGuiIO& io = ImGui::GetIO();
        io.ConfigFlags |= ImGuiConfigFlags_NavEnableKeyboard;
        io.ConfigFlags |= ImGuiConfigFlags_DockingEnable;
        io.Fonts->AddFontFromFileTTF("fonts/Roboto-Medium.ttf", 16.0f);
        
        // Setup backends
        ImGui_ImplGlfw_InitForOpenGL(window, true);
        ImGui_ImplOpenGL3_Init("#version 330");
        
        // Apply laboratory theme
        LabTheme::ApplyTheme();
        
        return true;
    }
    
    void Run() {
        while (!glfwWindowShouldClose(window)) {
            glfwPollEvents();
            
            // Start frame
            ImGui_ImplOpenGL3_NewFrame();
            ImGui_ImplGlfw_NewFrame();
            ImGui::NewFrame();
            
            // Main dockspace
            DrawDockspace();
            
            // Main menu bar
            DrawMenuBar();
            
            // Windows
            if (show_compound_editor) DrawCompoundEditor();
            if (show_simulation_control) DrawSimulationControl();
            if (show_live_metrics) DrawLiveMetrics();
            if (show_protocol_designer) DrawProtocolDesigner();
            if (show_population_stats) DrawPopulationStats();
            if (show_safety_analysis) DrawSafetyAnalysis();
            
            // Render
            ImGui::Render();
            int display_w, display_h;
            glfwGetFramebufferSize(window, &display_w, &display_h);
            glViewport(0, 0, display_w, display_h);
            glClearColor(LabTheme::BACKGROUND.x, LabTheme::BACKGROUND.y, 
                        LabTheme::BACKGROUND.z, LabTheme::BACKGROUND.w);
            glClear(GL_COLOR_BUFFER_BIT);
            ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());
            
            glfwSwapBuffers(window);
        }
    }
    
    void Shutdown() {
        ImGui_ImplOpenGL3_Shutdown();
        ImGui_ImplGlfw_Shutdown();
        ImPlot::DestroyContext();
        ImGui::DestroyContext();
        
        glfwDestroyWindow(window);
        glfwTerminate();
    }
    
private:
    void DrawDockspace() {
        ImGuiViewport* viewport = ImGui::GetMainViewport();
        ImGui::SetNextWindowPos(viewport->WorkPos);
        ImGui::SetNextWindowSize(viewport->WorkSize);
        ImGui::SetNextWindowViewport(viewport->ID);
        
        ImGuiWindowFlags window_flags = ImGuiWindowFlags_NoDocking | ImGuiWindowFlags_NoTitleBar |
                                        ImGuiWindowFlags_NoCollapse | ImGuiWindowFlags_NoResize |
                                        ImGuiWindowFlags_NoMove | ImGuiWindowFlags_NoBringToFrontOnFocus |
                                        ImGuiWindowFlags_NoNavFocus | ImGuiWindowFlags_NoBackground;
        
        ImGui::PushStyleVar(ImGuiStyleVar_WindowRounding, 0.0f);
        ImGui::PushStyleVar(ImGuiStyleVar_WindowBorderSize, 0.0f);
        ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(0.0f, 0.0f));
        
        ImGui::Begin("DockSpace", nullptr, window_flags);
        ImGui::PopStyleVar(3);
        
        ImGuiID dockspace_id = ImGui::GetID("MainDockSpace");
        ImGui::DockSpace(dockspace_id, ImVec2(0.0f, 0.0f), ImGuiDockNodeFlags_None);
        
        ImGui::End();
    }
    
    void DrawMenuBar() {
        if (ImGui::BeginMainMenuBar()) {
            if (ImGui::BeginMenu("System")) {
                if (ImGui::MenuItem("Compound Editor", nullptr, show_compound_editor)) {
                    show_compound_editor = !show_compound_editor;
                }
                if (ImGui::MenuItem("Simulation Control", nullptr, show_simulation_control)) {
                    show_simulation_control = !show_simulation_control;
                }
                if (ImGui::MenuItem("Live Metrics", nullptr, show_live_metrics)) {
                    show_live_metrics = !show_live_metrics;
                }
                ImGui::Separator();
                if (ImGui::MenuItem("Exit")) {
                    glfwSetWindowShouldClose(window, true);
                }
                ImGui::EndMenu();
            }
            
            if (ImGui::BeginMenu("Analysis")) {
                if (ImGui::MenuItem("Protocol Designer", nullptr, show_protocol_designer)) {
                    show_protocol_designer = !show_protocol_designer;
                }
                if (ImGui::MenuItem("Population Statistics", nullptr, show_population_stats)) {
                    show_population_stats = !show_population_stats;
                }
                if (ImGui::MenuItem("Safety Analysis", nullptr, show_safety_analysis)) {
                    show_safety_analysis = !show_safety_analysis;
                }
                ImGui::EndMenu();
            }
            
            if (ImGui::BeginMenu("View")) {
                if (ImGui::MenuItem("Dark Theme", nullptr, true)) {}
                if (ImGui::MenuItem("Reset Layout")) {}
                ImGui::EndMenu();
            }
            
            // Status indicators on the right
            ImGui::SetCursorPosX(ImGui::GetWindowWidth() - 300);
            if (sim_monitor.simulation_running) {
                ImGui::TextColored(LabTheme::SUCCESS_GREEN, "â— SIMULATION ACTIVE");
            } else {
                ImGui::TextColored(LabTheme::TEXT_DIM, "â— SIMULATION IDLE");
            }
            
            ImGui::EndMainMenuBar();
        }
    }
    
    void DrawCompoundEditor() {
        ImGui::Begin("Compound Profile Editor", &show_compound_editor);
        
        // Left panel - compound list
        ImGui::BeginChild("CompoundList", ImVec2(250, 0), true, ImGuiWindowFlags_HorizontalScrollbar);
        ImGui::TextColored(LabTheme::MERCURY_BLUE, "Compound Library");
        ImGui::Separator();
        
        for (size_t i = 0; i < compound_manager.compounds.size(); i++) {
            auto& comp = compound_manager.compounds[i];
            
            ImGui::PushID(i);
            bool selected = (compound_manager.selected_compound == i);
            
            // Safety indicator
            ImGui::TextColored(comp.safety_color, "â—");
            ImGui::SameLine();
            
            if (ImGui::Selectable(comp.name, selected)) {
                compound_manager.selected_compound = i;
            }
            
            if (ImGui::IsItemHovered()) {
                ImGui::BeginTooltip();
                ImGui::Text("Safety Score: %.0f%%", comp.safety_score);
                ImGui::Text("Bias Ratio: %.1f:1", comp.bias_ratio);
                ImGui::EndTooltip();
            }
            ImGui::PopID();
        }
        
        ImGui::Separator();
        if (ImGui::Button("+ Add Compound", ImVec2(-1, 0))) {
            CompoundManager::CompoundData new_comp;
            strcpy(new_comp.name, "New Compound");
            new_comp.ki_orthosteric = 50;
            new_comp.g_protein_bias = 1.0f;
            new_comp.beta_arrestin_bias = 1.0f;
            new_comp.t_half = 4.0f;
            new_comp.bioavailability = 0.7f;
            new_comp.intrinsic_activity = 0.5f;
            new_comp.tolerance_rate = 0.5f;
            new_comp.CalculateMetrics();
            compound_manager.compounds.push_back(new_comp);
        }
        
        ImGui::EndChild();
        ImGui::SameLine();
        
        // Right panel - editor
        ImGui::BeginChild("Editor", ImVec2(0, 0), true);
        
        if (compound_manager.selected_compound >= 0 && 
            compound_manager.selected_compound < compound_manager.compounds.size()) {
            
            auto& comp = compound_manager.compounds[compound_manager.selected_compound];
            
            // Header with safety score
            ImGui::TextColored(LabTheme::MERCURY_BLUE, "Editing: %s", comp.name);
            ImGui::SameLine(ImGui::GetWindowWidth() - 200);
            ImGui::TextColored(comp.safety_color, "Safety: %.0f%%", comp.safety_score);
            ImGui::Separator();
            
            // Basic info
            ImGui::InputText("Name", comp.name, sizeof(comp.name));
            
            // Expandable sections
            if (ImGui::CollapsingHeader("Binding Parameters", expand_binding_params ? 
                                        ImGuiTreeNodeFlags_DefaultOpen : 0)) {
                
                ImGui::TextColored(LabTheme::TEXT_DIM, "Affinities in nM (0 = no binding)");
                
                ImGui::PushItemWidth(200);
                ImGui::DragFloat("Ki Orthosteric", &comp.ki_orthosteric, 1.0f, 0, 1000, "%.1f nM");
                DrawParameterHelp("Traditional binding site. Lower = stronger. Morphine = 1.8 nM");
                
                ImGui::DragFloat("Ki Allosteric 1", &comp.ki_allosteric1, 1.0f, 0, 1000, "%.1f nM");
                DrawParameterHelp("Primary allosteric site. Doesn't compete with endorphins.");
                
                ImGui::DragFloat("Ki Allosteric 2", &comp.ki_allosteric2, 1.0f, 0, 1000, "%.1f nM");
                DrawParameterHelp("Secondary allosteric site for fine-tuning.");
                ImGui::PopItemWidth();
            }
            
            if (ImGui::CollapsingHeader("Signaling Properties", expand_signaling_params ?
                                        ImGuiTreeNodeFlags_DefaultOpen : 0)) {
                
                ImGui::PushItemWidth(200);
                ImGui::SliderFloat("G-Protein Bias", &comp.g_protein_bias, 0.1f, 20.0f, "%.1f");
                DrawParameterHelp("Higher = more analgesia, less respiratory depression. Target >5");
                DrawBiasIndicator(comp.g_protein_bias);
                
                ImGui::SliderFloat("Î²-Arrestin Bias", &comp.beta_arrestin_bias, 0.01f, 2.0f, "%.2f");
                DrawParameterHelp("Lower = less tolerance/addiction. Target <0.3");
                
                // Bias ratio visualization
                float ratio = comp.g_protein_bias / (comp.beta_arrestin_bias + 0.001f);
                ImGui::TextColored(ratio > 10 ? LabTheme::SUCCESS_GREEN : 
                                  ratio > 5 ? LabTheme::WARNING_AMBER : LabTheme::DANGER_RED,
                                  "Bias Ratio: %.1f:1", ratio);
                ImGui::PopItemWidth();
            }
            
            if (ImGui::CollapsingHeader("Pharmacokinetics", expand_pk_params ?
                                        ImGuiTreeNodeFlags_DefaultOpen : 0)) {
                
                ImGui::PushItemWidth(200);
                ImGui::SliderFloat("Half-life (hours)", &comp.t_half, 0.5f, 48.0f, "%.1f h");
                DrawParameterHelp("2-4h for breakthrough, 8-12h for maintenance");
                
                ImGui::SliderFloat("Bioavailability", &comp.bioavailability, 0.1f, 1.0f, "%.2f");
                DrawParameterHelp("Oral absorption. >0.5 for predictable response");
                
                ImGui::SliderFloat("Intrinsic Activity", &comp.intrinsic_activity, 0.0f, 1.0f, "%.2f");
                DrawParameterHelp("0=antagonist, 0.3-0.5=partial (safe), 1=full agonist");
                
                ImGui::SliderFloat("Tolerance Rate", &comp.tolerance_rate, 0.0f, 1.0f, "%.2f");
                DrawParameterHelp("Speed of tolerance development. <0.3 for chronic use");
                ImGui::PopItemWidth();
            }
            
            if (ImGui::CollapsingHeader("Special Properties", expand_special_props ?
                                        ImGuiTreeNodeFlags_DefaultOpen : 0)) {
                
                ImGui::Checkbox("Prevents Withdrawal", &comp.prevents_withdrawal);
                DrawParameterHelp("Critical for maintenance therapy and switching");
                
                ImGui::Checkbox("Reverses Tolerance", &comp.reverses_tolerance);
                DrawParameterHelp("Revolutionary if true (SR-17018-like property)");
            }
            
            // Recalculate metrics
            comp.CalculateMetrics();
            
            // Safety analysis panel
            ImGui::Separator();
            DrawCompoundSafetyAnalysis(comp);
        }
        
        ImGui::EndChild();
        ImGui::End();
    }
    
    void DrawSimulationControl() {
        ImGui::Begin("Simulation Control", &show_simulation_control);
        
        // Mercury arc rectifier visualization
        ImGui::Columns(2, nullptr, false);
        
        // Left column - rectifier
        sim_monitor.arc_rectifier.SetIntensity(sim_monitor.simulation_running ? 
            (float)sim_monitor.metrics.patients_processed / sim_monitor.metrics.total_patients : 0);
        sim_monitor.arc_rectifier.Draw("PROCESS", ImVec2(100, 180));
        
        // Right column - controls
        ImGui::NextColumn();
        
        ImGui::TextColored(LabTheme::MERCURY_BLUE, "100K Patient Simulation");
        ImGui::Separator();
        
        // Protocol configuration
        ImGui::Text("Protocol Configuration:");
        ImGui::PushItemWidth(150);
        ImGui::DragFloat("SR-17018 (mg)", &current_protocol.sr17018_dose, 0.1f, 0, 100);
        ImGui::DragFloat("SR-14968 (mg)", &current_protocol.sr14968_dose, 0.1f, 0, 100);
        ImGui::DragFloat("DPP-26 (mg)", &current_protocol.dpp26_dose, 0.1f, 0, 50);
        ImGui::PopItemWidth();
        
        ImGui::Separator();
        
        // Control buttons
        if (!sim_monitor.simulation_running) {
            if (ImGui::Button("START SIMULATION", ImVec2(200, 40))) {
                sim_monitor.StartSimulation(current_protocol);
            }
        } else {
            if (ImGui::Button("STOP SIMULATION", ImVec2(200, 40))) {
                sim_monitor.StopSimulation();
            }
            
            // Progress bar
            float progress = (float)sim_monitor.metrics.patients_processed / 
                           sim_monitor.metrics.total_patients;
            ImGui::ProgressBar(progress, ImVec2(200, 20), 
                              std::to_string(sim_monitor.metrics.patients_processed).c_str());
        }
        
        // Quick stats
        ImGui::Separator();
        ImGui::Text("Current Metrics:");
        ImGui::TextColored(LabTheme::SUCCESS_GREEN, "Success: %.1f%%", 
                          sim_monitor.metrics.current_success * 100);
        ImGui::TextColored(sim_monitor.metrics.current_tolerance < 0.05f ? 
                          LabTheme::SUCCESS_GREEN : LabTheme::WARNING_AMBER,
                          "Tolerance: %.1f%%", sim_monitor.metrics.current_tolerance * 100);
        ImGui::TextColored(sim_monitor.metrics.current_addiction < 0.03f ? 
                          LabTheme::SUCCESS_GREEN : LabTheme::DANGER_RED,
                          "Addiction: %.1f%%", sim_monitor.metrics.current_addiction * 100);
        
        ImGui::Columns(1);
        ImGui::End();
    }
    
    void DrawLiveMetrics() {
        ImGui::Begin("Live Metrics Dashboard", &show_live_metrics);
        
        if (ImPlot::BeginPlot("Real-Time Outcomes", ImVec2(-1, 300))) {
            ImPlot::SetupAxes("Batch", "Rate (%)", ImPlotAxisFlags_AutoFit, ImPlotAxisFlags_AutoFit);
            ImPlot::SetupAxisLimits(ImAxis_Y1, 0, 100);
            
            if (!sim_monitor.metrics.analgesia_history.empty()) {
                std::vector<float> x_data(sim_monitor.metrics.analgesia_history.size());
                for (size_t i = 0; i < x_data.size(); i++) x_data[i] = i;
                
                ImPlot::SetNextLineStyle(LabTheme::SUCCESS_GREEN);
                ImPlot::PlotLine("Analgesia", x_data.data(), 
                                 sim_monitor.metrics.analgesia_history.data(), x_data.size());
                
                ImPlot::SetNextLineStyle(LabTheme::WARNING_AMBER);
                ImPlot::PlotLine("Tolerance", x_data.data(),
                                 sim_monitor.metrics.tolerance_history.data(), x_data.size());
                
                ImPlot::SetNextLineStyle(LabTheme::DANGER_RED);
                ImPlot::PlotLine("Addiction", x_data.data(),
                                 sim_monitor.metrics.addiction_history.data(), x_data.size());
                
                ImPlot::SetNextLineStyle(LabTheme::MERCURY_BLUE);
                ImPlot::PlotLine("Success Rate", x_data.data(),
                                 sim_monitor.metrics.success_rate_history.data(), x_data.size());
            }
            
            ImPlot::EndPlot();
        }
        
        // Target achievement indicators
        ImGui::Separator();
        ImGui::TextColored(LabTheme::MERCURY_BLUE, "Target Achievement:");
        
        bool tolerance_met = sim_monitor.metrics.current_tolerance < 0.05f;
        bool addiction_met = sim_monitor.metrics.current_addiction < 0.03f;
        bool success_met = sim_monitor.metrics.current_success > 0.7f;
        
        ImGui::TextColored(tolerance_met ? LabTheme::SUCCESS_GREEN : LabTheme::DANGER_RED,
                          "%s Tolerance < 5%%", tolerance_met ? "âœ“" : "âœ—");
        ImGui::TextColored(addiction_met ? LabTheme::SUCCESS_GREEN : LabTheme::DANGER_RED,
                          "%s Addiction < 3%%", addiction_met ? "âœ“" : "âœ—");
        ImGui::TextColored(success_met ? LabTheme::SUCCESS_GREEN : LabTheme::DANGER_RED,
                          "%s Success > 70%%", success_met ? "âœ“" : "âœ—");
        
        ImGui::End();
    }
    
    void DrawProtocolDesigner() {
        ImGui::Begin("Protocol Designer", &show_protocol_designer);
        
        ImGui::TextColored(LabTheme::MERCURY_BLUE, "Multi-Compound Protocol Optimization");
        ImGui::Separator();
        
        static int protocol_type = 0;
        ImGui::RadioButton("Maximum Safety", &protocol_type, 0);
        ImGui::RadioButton("Breakthrough Pain", &protocol_type, 1);
        ImGui::RadioButton("Opioid Rotation", &protocol_type, 2);
        ImGui::RadioButton("Custom", &protocol_type, 3);
        
        ImGui::Separator();
        
        // Compound selection
        static int comp1_idx = 0, comp2_idx = 1, comp3_idx = 2;
        
        ImGui::Text("Select Compounds:");
        ImGui::PushItemWidth(200);
        
        if (ImGui::BeginCombo("Compound 1", 
                             comp1_idx < compound_manager.compounds.size() ?
                             compound_manager.compounds[comp1_idx].name : "None")) {
            for (size_t i = 0; i < compound_manager.compounds.size(); i++) {
                if (ImGui::Selectable(compound_manager.compounds[i].name, comp1_idx == i)) {
                    comp1_idx = i;
                }
            }
            ImGui::EndCombo();
        }
        
        if (ImGui::BeginCombo("Compound 2",
                             comp2_idx < compound_manager.compounds.size() ?
                             compound_manager.compounds[comp2_idx].name : "None")) {
            for (size_t i = 0; i < compound_manager.compounds.size(); i++) {
                if (ImGui::Selectable(compound_manager.compounds[i].name, comp2_idx == i)) {
                    comp2_idx = i;
                }
            }
            ImGui::EndCombo();
        }
        
        if (ImGui::BeginCombo("Compound 3",
                             comp3_idx < compound_manager.compounds.size() ?
                             compound_manager.compounds[comp3_idx].name : "None")) {
            for (size_t i = 0; i < compound_manager.compounds.size(); i++) {
                if (ImGui::Selectable(compound_manager.compounds[i].name, comp3_idx == i)) {
                    comp3_idx = i;
                }
            }
            ImGui::EndCombo();
        }
        
        ImGui::PopItemWidth();
        
        ImGui::Separator();
        
        if (ImGui::Button("Optimize Protocol", ImVec2(200, 30))) {
            // Run optimization
        }
        
        ImGui::End();
    }
    
    void DrawPopulationStats() {
        ImGui::Begin("Population Statistics", &show_population_stats);
        
        ImGui::TextColored(LabTheme::MERCURY_BLUE, "Statistical Analysis");
        ImGui::Separator();
        
        // Placeholder for detailed statistics
        ImGui::Text("Efficacy Metrics:");
        ImGui::BulletText("Treatment Success: %.1f%%", 70.2f);
        ImGui::BulletText("Mean Pain Reduction: %.1f%%", 68.5f);
        
        ImGui::Separator();
        ImGui::Text("Safety Metrics:");
        ImGui::BulletText("Tolerance Rate: %.1f%%", 4.8f);
        ImGui::BulletText("Addiction Rate: %.1f%%", 2.9f);
        ImGui::BulletText("Withdrawal Rate: %.1f%%", 0.1f);
        
        ImGui::End();
    }
    
    void DrawSafetyAnalysis() {
        ImGui::Begin("Safety Analysis", &show_safety_analysis);
        
        ImGui::TextColored(LabTheme::MERCURY_BLUE, "Comprehensive Safety Assessment");
        ImGui::Separator();
        
        // Safety matrix
        if (ImGui::BeginTable("SafetyMatrix", 4, ImGuiTableFlags_Borders | ImGuiTableFlags_RowBg)) {
            ImGui::TableSetupColumn("Compound");
            ImGui::TableSetupColumn("Safety Score");
            ImGui::TableSetupColumn("Bias Ratio");
            ImGui::TableSetupColumn("Risk Level");
            ImGui::TableHeadersRow();
            
            for (const auto& comp : compound_manager.compounds) {
                ImGui::TableNextRow();
                ImGui::TableNextColumn();
                ImGui::Text("%s", comp.name);
                
                ImGui::TableNextColumn();
                ImGui::TextColored(comp.safety_color, "%.0f%%", comp.safety_score);
                
                ImGui::TableNextColumn();
                ImGui::Text("%.1f:1", comp.bias_ratio);
                
                ImGui::TableNextColumn();
                const char* risk = comp.safety_score > 80 ? "Low" : 
                                  comp.safety_score > 60 ? "Moderate" : "High";
                ImGui::TextColored(comp.safety_color, "%s", risk);
            }
            
            ImGui::EndTable();
        }
        
        ImGui::End();
    }
    
    // Helper functions
    void DrawParameterHelp(const char* text) {
        ImGui::SameLine();
        ImGui::TextColored(LabTheme::TEXT_DIM, "(?)");
        if (ImGui::IsItemHovered()) {
            ImGui::BeginTooltip();
            ImGui::PushTextWrapPos(ImGui::GetFontSize() * 35.0f);
            ImGui::Text("%s", text);
            ImGui::PopTextWrapPos();
            ImGui::EndTooltip();
        }
    }
    
    void DrawBiasIndicator(float bias) {
        ImGui::SameLine();
        if (bias > 10) {
            ImGui::TextColored(LabTheme::SUCCESS_GREEN, "Excellent");
        } else if (bias > 5) {
            ImGui::TextColored(LabTheme::WARNING_AMBER, "Good");
        } else {
            ImGui::TextColored(LabTheme::DANGER_RED, "Poor");
        }
    }
    
    void DrawCompoundSafetyAnalysis(const CompoundManager::CompoundData& comp) {
        ImGui::TextColored(LabTheme::MERCURY_BLUE, "Safety Analysis:");
        
        // Safety indicators
        bool safe_bias = comp.bias_ratio > 5;
        bool safe_activity = comp.intrinsic_activity <= 0.6;
        bool safe_tolerance = comp.tolerance_rate < 0.3;
        bool safe_pk = comp.t_half >= 4 && comp.bioavailability > 0.3;
        
        ImGui::TextColored(safe_bias ? LabTheme::SUCCESS_GREEN : LabTheme::DANGER_RED,
                          "%s Bias Ratio > 5:1", safe_bias ? "âœ“" : "âœ—");
        ImGui::TextColored(safe_activity ? LabTheme::SUCCESS_GREEN : LabTheme::WARNING_AMBER,
                          "%s Ceiling Effect Present", safe_activity ? "âœ“" : "âœ—");
        ImGui::TextColored(safe_tolerance ? LabTheme::SUCCESS_GREEN : LabTheme::WARNING_AMBER,
                          "%s Low Tolerance Risk", safe_tolerance ? "âœ“" : "âœ—");
        ImGui::TextColored(safe_pk ? LabTheme::SUCCESS_GREEN : LabTheme::WARNING_AMBER,
                          "%s Stable Pharmacokinetics", safe_pk ? "âœ“" : "âœ—");
    }
};

// ============================================================================
// MAIN ENTRY POINT
// ============================================================================

int main(int argc, char** argv) {
    ZeroPainControlPanel app;
    
    if (!app.Init()) {
        std::cerr << "Failed to initialize application\n";
        return -1;
    }
    
    app.Run();
    app.Shutdown();
    
    return 0;
}