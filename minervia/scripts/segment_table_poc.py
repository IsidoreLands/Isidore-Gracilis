#!/usr/bin/env python3
import cv2
import os
import numpy as np

# --- Configuration ---
IMAGE_FILENAME = "01_source_pngs/page-001.png"
OUTPUT_DIR = "poc_output"
BINARIZED_BASE_FILENAME = "binarized_page-001" 
GRAYSCALE_BASE_FILENAME = "grayscale_page-001" # Added back for consistency in process_image_initial
PROCESSED_LINES_BASE_FILENAME = "processed_lines_page-001"
CELL_GRID_BASE_FILENAME = "cell_grid_page-001" 
EXTRACTED_SYMBOLS_DIR = os.path.join(OUTPUT_DIR, "extracted_symbols")

# Best parameters from L1C
HOUGH_MIN_LINE_LENGTH = 75
HOUGH_THRESHOLD = 100
HOUGH_MAX_LINE_GAP = 20
H_LINE_MERGE_TOLERANCE = 15
V_LINE_MERGE_TOLERANCE = 5 # Renamed from V_LINE_MERGE_TOLERANCE_TO_TEST for simplicity
SYMBOL_COLUMN_INDICES = [1, 3] # Based on visual inspection of 5-column grid from MLL=75, VTOL=5

def process_detected_lines(lines, is_horizontal, tolerance=10):
    # (Unchanged)
    if not lines: return []
    representative_coords = []
    if is_horizontal:
        coords_with_orig = [((line[1] + line[3]) // 2, line) for line in lines]
        coords_with_orig.sort(key=lambda item: item[0])
    else:
        coords_with_orig = [((line[0] + line[2]) // 2, line) for line in lines]
        coords_with_orig.sort(key=lambda item: item[0])
    if not coords_with_orig: return []
    merged_coords = [coords_with_orig[0][0]] 
    for current_coord, _ in coords_with_orig[1:]:
        if abs(current_coord - merged_coords[-1]) > tolerance:
            merged_coords.append(current_coord)
    return sorted(list(set(merged_coords)))

def detect_and_process_lines(binarized_image_path, original_image_path_for_drawing, 
                             hough_min_line_length, 
                             h_line_tolerance, v_line_tolerance, # This v_line_tolerance is passed
                             output_suffix=""): 
    bin_img = cv2.imread(binarized_image_path, cv2.IMREAD_GRAYSCALE)
    if bin_img is None: print(f"Error: Could not load binarized image from {binarized_image_path}"); return [], [], None
    img_for_drawing_lines = cv2.imread(original_image_path_for_drawing) 
    if img_for_drawing_lines is None:
        print(f"Error: Could not load original image for drawing lines from {original_image_path_for_drawing}")
        img_for_drawing_lines = cv2.cvtColor(bin_img, cv2.COLOR_GRAY2BGR)

    rho = 1; theta = np.pi / 180 # Using global HOUGH_THRESHOLD, HOUGH_MAX_LINE_GAP
    raw_lines = cv2.HoughLinesP(bin_img, rho, theta, HOUGH_THRESHOLD, None, 
                                hough_min_line_length, HOUGH_MAX_LINE_GAP)
    raw_horizontal_segments = []; raw_vertical_segments = []
    if raw_lines is not None:
        for i in range(0, len(raw_lines)):
            l = raw_lines[i][0]; x1, y1, x2, y2 = l
            angle = np.arctan2(y2 - y1, x2 - x1) * 180. / np.pi; line_len = np.sqrt((x2-x1)**2 + (y2-y1)**2)
            if abs(angle) < 5 and line_len > 200: 
                raw_horizontal_segments.append(l)
            elif abs(abs(angle) - 90) < 5: 
                raw_vertical_segments.append(l)
        
        processed_h_coords = process_detected_lines(raw_horizontal_segments, is_horizontal=True, tolerance=h_line_tolerance)
        processed_v_coords = process_detected_lines(raw_vertical_segments, is_horizontal=False, tolerance=v_line_tolerance) # Uses passed v_line_tolerance
        
        print(f"Raw classified: {len(raw_horizontal_segments)} H, {len(raw_vertical_segments)} V")
        print(f"Processed to {len(processed_h_coords)} unique H-lines (tolerance={h_line_tolerance}).")
        print(f"Processed to {len(processed_v_coords)} unique V-lines (tolerance={v_line_tolerance}).") # Prints passed v_line_tolerance
        
        # Optionally save processed lines image
        # img_for_processed_lines_display = img_for_drawing_lines.copy()
        # ... drawing code ...
        # processed_lines_output_path = os.path.join(OUTPUT_DIR, f"{PROCESSED_LINES_BASE_FILENAME}{output_suffix}.png")
        # cv2.imwrite(processed_lines_output_path, img_for_processed_lines_display)
        # print(f"Saved image with processed lines to: {processed_lines_output_path}")
        
        return processed_h_coords, processed_v_coords, bin_img 
    else:
        print(f"No raw lines were detected (MLL={hough_min_line_length})."); return [], [], None

def process_image_initial(image_path):
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR); print(f"Created directory: {OUTPUT_DIR}")
    img = cv2.imread(image_path)
    if img is None: print(f"Error: Could not load image from {image_path}"); return None
    
    gray_path = os.path.join(OUTPUT_DIR, GRAYSCALE_BASE_FILENAME + ".png") 
    bin_path = os.path.join(OUTPUT_DIR, BINARIZED_BASE_FILENAME + ".png")   

    if not (os.path.exists(gray_path) and os.path.exists(bin_path)): # Process only if both don't exist
        print(f"Performing initial grayscale and binarization...")
        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        cv2.imwrite(gray_path, gray_img)
        print(f"Saved grayscale image to: {gray_path}")
        binarized_img_data = cv2.adaptiveThreshold(gray_img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
        cv2.imwrite(bin_path, binarized_img_data)
        print(f"Saved binarized image to: {bin_path}")
    else:
        print(f"Using existing grayscale ({gray_path}) and binarized ({bin_path}) images.")
    return bin_path

def define_cells_and_extract_symbols(processed_h_coords, processed_v_coords, 
                                     image_to_crop_from, 
                                     original_image_for_drawing_grid, 
                                     output_suffix_params=""): # Suffix for filenames
    img_for_grid_drawing = cv2.imread(original_image_for_drawing_grid)
    if img_for_grid_drawing is None: print(f"Error loading image for drawing grid: {original_image_for_drawing_grid}"); return [], []

    cell_grid_output_path = os.path.join(OUTPUT_DIR, f"{CELL_GRID_BASE_FILENAME}{output_suffix_params}.png")

    if not processed_h_coords or len(processed_h_coords) < 2 or \
       not processed_v_coords or len(processed_v_coords) < 2:
        print("Not enough H or V lines to define cells."); cv2.imwrite(cell_grid_output_path, img_for_grid_drawing); return [], []
        
    num_rows = len(processed_h_coords) - 1
    num_cols = len(processed_v_coords) - 1
    print(f"Defining grid with {num_rows} rows and {num_cols} columns.")
    
    cell_coordinates = []
    extracted_symbol_count = 0
    if not os.path.exists(EXTRACTED_SYMBOLS_DIR):
        os.makedirs(EXTRACTED_SYMBOLS_DIR)
        print(f"Created directory: {EXTRACTED_SYMBOLS_DIR}")

    for r_idx in range(num_rows):
        y_start = processed_h_coords[r_idx]
        y_end = processed_h_coords[r_idx+1]
        for c_idx in range(num_cols):
            x_start = processed_v_coords[c_idx]
            x_end = processed_v_coords[c_idx+1]
            
            if x_start < x_end and y_start < y_end: 
                cv2.rectangle(img_for_grid_drawing, (x_start, y_start), (x_end, y_end), (0,0,255), 1) 
                cell_info = {"row": r_idx, "col": c_idx, "x1": x_start, "y1": y_start, "x2": x_end, "y2": y_end}
                cell_coordinates.append(cell_info)
                
                if c_idx in SYMBOL_COLUMN_INDICES:
                    symbol_crop = image_to_crop_from[y_start:y_end, x_start:x_end]
                    if symbol_crop.size > 0:
                        symbol_filename = f"symbol_r{r_idx:02d}_c{c_idx:02d}{output_suffix_params}.png"
                        symbol_filepath = os.path.join(EXTRACTED_SYMBOLS_DIR, symbol_filename)
                        cv2.imwrite(symbol_filepath, symbol_crop)
                        extracted_symbol_count += 1
                    else: print(f"Warning: Empty crop for cell r{r_idx}_c{c_idx}")
            else: print(f"Warning: Invalid cell coordinates for r{r_idx}_c{c_idx}")

    cv2.imwrite(cell_grid_output_path, img_for_grid_drawing)
    print(f"Saved image with cell grid to: {cell_grid_output_path}")
    print(f"Extracted {extracted_symbol_count} symbol images to '{EXTRACTED_SYMBOLS_DIR}'.")
    return cell_coordinates

if __name__ == "__main__":
    if not os.path.exists(IMAGE_FILENAME):
        print(f"Error: Input image not found at {IMAGE_FILENAME}")
    else:
        print("Ensuring initial image processing (grayscale and binarization)...")
        binarized_image_filepath = process_image_initial(IMAGE_FILENAME)
        if binarized_image_filepath is None: print("Exiting due to error in initial image processing."); exit()
        
        binarized_img_data_for_cropping = cv2.imread(binarized_image_filepath, cv2.IMREAD_GRAYSCALE)
        if binarized_img_data_for_cropping is None:
            print(f"Error: Failed to load binarized image {binarized_image_filepath} for cropping."); exit()
        
        print(f"Using binarized image: {binarized_image_filepath}")

        # Use the globally defined parameters
        mll_to_use = HOUGH_MIN_LINE_LENGTH 
        v_tol_to_use = V_LINE_MERGE_TOLERANCE # Corrected variable name here
        h_tol_to_use = H_LINE_MERGE_TOLERANCE

        # Construct a suffix string based on the parameters being used for this run
        param_suffix = f"_MLL{mll_to_use}_HTOL{h_tol_to_use}_VTOL{v_tol_to_use}"

        h_coords, v_coords, binarized_img_data_from_detection = detect_and_process_lines(
            binarized_image_filepath, 
            IMAGE_FILENAME, 
            hough_min_line_length=mll_to_use,
            h_line_tolerance=h_tol_to_use, 
            v_line_tolerance=v_tol_to_use,
            output_suffix=param_suffix 
        )
        
        if h_coords and v_coords and binarized_img_data_from_detection is not None:
            print(f"Parameters used: MLL={mll_to_use}, HTOL={h_tol_to_use}, VTOL={v_tol_to_use}")
            print(f"Proceeding to define cells and extract symbols with {len(h_coords)} H-lines and {len(v_coords)} V-lines.")
            
            cells = define_cells_and_extract_symbols(
                h_coords, v_coords, 
                binarized_img_data_for_cropping, 
                IMAGE_FILENAME, 
                output_suffix_params=param_suffix
            )
            if cells:
                print(f"Identified {len(cells)} total cells. Extracted symbols from columns: {SYMBOL_COLUMN_INDICES}.")
        else:
            print(f"Could not proceed to define cells. Parameters: MLL={mll_to_use}, HTOL={h_tol_to_use}, VTOL={v_tol_to_use}.")
        print("-" * 40)

